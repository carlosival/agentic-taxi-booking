from pydantic import ValidationError
from yaafpy.types import AgentConfig, ExecContext, WorkflowAbortException
from yaafpy.workflows import Workflow
from utils.utils import json_parser
from langchain_ollama import ChatOllama
import logging
from ._memory import RedisMemory
from ._state import RedisState, BookingState, InputData
import json
from services.geolocation_service import MapboxService
from services.booking_service import BookingService
from datetime import datetime
from typing import Iterable
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import os



def user_input_guardrail(ctx: ExecContext) -> ExecContext:
    return ctx


async def load_data(ctx: ExecContext) -> ExecContext:

    if not ctx.session_id:
        ctx.error = "Not session_id set"
        ctx.stop = True
        return ctx
    
    user_input = ctx.input.input

    memory = RedisMemory(session_id=ctx.session_id)
    booking_state = RedisState(session_id=ctx.session_id)
    # could be move to another middleware
    ctx.storage["message"] = await memory.get_messages(limit=100)
    ctx.state = (await booking_state.get_state()).model_dump()
    
    # could be move to another middleware
    ctx.storage.setdefault("delta_message", []).append({"role":"user","content":user_input})
    
    return ctx

def add_message(ctx: ExecContext) -> ExecContext:
        
        if not ctx.session_id:
            ctx.error = "Not session_id set"
            ctx.stop = True
            return ctx

        action = ctx.output.get("action", None)
        content =  ctx.output.get("args", None)
        role = "ai"

        ctx.storage.setdefault("delta_message", []).append({'role':role,'content':content,'action':action})
        return ctx

async def persist_message(ctx:ExecContext) -> ExecContext:
        try:
            if not ctx.session_id:
                ctx.error = "Not session_id set"
                ctx.stop = True
                return ctx
            

            memory = RedisMemory(session_id=ctx.session_id)
           
            #merge and persist message
            ctx.storage["message"] = await memory._add_messages_and_get_all(ctx.storage.get("delta_message",[]))
            ctx.storage["delta_message"] = []
        
            return ctx
        
        except Exception as error:
            print(error)
            raise WorkflowAbortException("Error Persisting message")

async def persist_state(ctx:ExecContext) -> ExecContext:
        try:
            if not ctx.session_id:
                ctx.error = "Not session_id set"
                ctx.stop = True
                return ctx
            
            booking_state = RedisState(session_id=ctx.session_id)

            
            #Merge delta state with state
            merge = ctx.state | ctx.storage.get("delta_state", {})

            res = await booking_state.set_state(BookingState(**merge))

            if res:
                ctx.state = merge
                ctx.storage.setdefault("delta_state",None)

            return ctx
        
        except Exception as error:
            print(error)
            raise WorkflowAbortException("Error Saving data")

def _valid_dict(dictionary: dict, fields: Iterable, require_all: bool = True) -> bool:
    checker = all if require_all else any
    return checker(field in dictionary for field in fields)


def time_output_guardrail(ctx: ExecContext) -> ExecContext:
     
    valid = _valid_dict(ctx.output,[])

    if valid:
        ctx.storage["delta_pickup_time"] = ctx.output
        return ctx
    
    raise WorkflowAbortException("Error time_agent output")

def follow_up_processing(ctx: ExecContext) -> ExecContext:
        
        # Check response_to_user action exits
        print(ctx.output.get("response_to_user"), "Could not find the 'response_to_user'")
        
        return ctx
        

def state_output_guardrail(ctx: ExecContext) -> ExecContext:
    
    if not ctx.session_id:
        ctx.error = "Not session_id set"
        ctx.stop = True
        return ctx

    if ctx.stop:
        return ctx

    try:
        # Validamos los datos extraídos por el LLM
        new_data = BookingState(**ctx.output.get("args", {}))
        
        # Usamos exclude_unset=True para no incluir campos vacíos por defecto
        delta_state = new_data.model_dump(exclude_unset=True)

        # Si pasa la validación, actualizamos el estado real
        # .dict(exclude_unset=True) evita sobreescribir con Nones lo que el LLM no mencionó
        #ctx.state.update(new_data.dict(exclude_unset=True)) que this for final update
        ctx.storage.setdefault("delta_state", {}).update(delta_state)
        
        return ctx
    
    except ValidationError as e:
        print(f"El LLM envió datos inválidos: {e}")
        ctx.error=f"El LLM envió datos inválidos: {e}"
        ctx.stop=True
        ctx.output="No es posible procesar su respuesta ahora. Refrase"        
        return ctx


def _build_context(messages: list) -> str:
        """Build conversation as string"""
        try:
            context_parts = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                action = msg.get("action", None)
                if not action or action == "respond_to_user":
                    context_parts.append(f"{role}: {content}")
            return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error building context: {e}")
            return ""

async def build_prompt_follow_up(ctx: ExecContext) -> ExecContext:
    if not ctx.session_id:
        ctx.error = "Not session_id set"
        ctx.stop = True
        return ctx
    
    # Merge Message
    all_messages = ctx.storage.get("message", [])
    delta_message = ctx.storage.get("delta_message", [])
    all_messages.extend(delta_message)
    
    #Merge delta state with state
    merge_state = ctx.state | ctx.storage.get("delta_state", {})

    if all_messages is None:
        logger.error(f"Failed to retrieve messages")
        ctx.error = "I'm having trouble accessing our conversation. Could you please repeat your request?"
        ctx.stop = True   
        return ctx 
    
    context = _build_context(all_messages)

    # Build prompt for follow-up questions
    current_state = ctx.state
    if not current_state:
        logger.error(f"Failed to get current booking state")
        ctx.error = "Failed to get current booking state"
        ctx.stop = True
        return ctx
    
    ctx.agent.prompt = f"""
    System:    
        - You are a helpful and courteous taxi booking assistant. 
        - Your job is to guide the user step by step to book a taxi, using a clear and friendly conversation.

    💬 Language:
    - Detect and use the language the user prefers (e.g., English, Spanish).
    - Always speak in simple, polite, and natural language.

    🗂️ **Memory:**
    - Use the conversation history to remember what the user has already told you.
    - Use the Current Booking State to know exactly which details are missing.
    - Any field with `None`, `null`, or `false` counts as missing.
    - Never ask for the same information twice.
    - Ask for **only one missing detail at a time**.

    ⚙️ Context (conversation history):
    {context}

    Current Booking State (JSON FORMAT):
    {json.dumps(merge_state)}

    Your task:
    - Review the current booking state and the conversation context below.
    - Identify the **next missing detail**, in this order:
    1. pickup_location
    2. destination
    3. pickup_time
    4. special_requests
    5. confirmed

    - If `special_requests` is `"N/A"` or empty, treat it as *no special request* — do NOT ask for it again, proceed to confirmation.
    - Politely ask the user for **only one missing piece of information at a time**.


    📏 Response rules:
    - Respond with exactly **one valid JSON object** in this format:
    {{
        "action": "respond_to_user",
        "args": "<your polite question here>"
    }}

    - Do NOT include any extra text, comments, or formatting outside the JSON object.
    - Phrase your question clearly and politely.
    - If all required details are present except confirmed, provide a short, friendly summary using the current booking state and politely ask the user to confirm or change anything if needed.

    🔒 Example valid response:
    {{
    "action": "respond_to_user",
    "args": "Could you please tell me where you would like to be picked up?"
    }}

    Only produce the JSON object. Do not add any other text.
    """

    return ctx
    
async def build_prompt_get_update_info(ctx: ExecContext) -> ExecContext:

    user_input = ctx.input.input
    all_messages = ctx.storage.get("message", None) 
    
    if all_messages is None:
        logger.error(f"Failed to retrieve messages")
        ctx.error = "I'm having trouble accessing our conversation. Could you please repeat your request?"
        ctx.stop = True   
        return ctx 
    
    # Get last system question if any
    question = ""
    for msg in reversed(all_messages):
        if msg.get("role") == "ai" and msg.get("action") == "respond_to_user":
            question = msg.get("content", "")
            break

    current_state = BookingState(**ctx.state).model_dump_json(exclude_none=False)        

    ctx.agent.prompt = f"""
            ### ROLE
            You are a specialized Data Extraction Engine for a Taxi Booking System. Your sole purpose is to parse user input and update the booking state JSON.

            ### TASK
            1. Analyze the {question} sent by the system and the {user_input} provided by the user.
            2. Compare this with the {current_state}.
            3. Extract new or updated information for the following fields:
            - pickup_location
                - If the information is missing entirely, omit the field from "args".
            - destination
                - If the information is missing entirely, omit the field from "args".
            - pickup_time
                - If the information is missing entirely, omit the field from "args".
            - special_requests
                - If the user provides a specific request, extract it.
                - If the user says they have no requests (e.g., "no", "none"), set this field to "N/A".
                - If the user gives a vague answer (e.g., "as usual", "you know"), set this field to null.
                - If the information is missing entirely, omit the field from "args".
            - confirmed (Boolean. ONLY if the user says "yes"/"no" or equivalents like "confirmado"/"cancelar". Do NOT use for "ok" or "thanks").
                - If the information is missing entirely, omit the field from "args".
            ### CONSTRAINTS
            - **Zero Hallucination:** Never guess or assume data. If a field isn't explicitly mentioned in {user_input}, do not include it in the `args` object.
            - **Output Format:** Return ONLY a valid JSON object. No conversational filler, no markdown blocks, no explanations.
            - **Language Neutrality:** Extract data regardless of the language used, but keep the values concise.

            ### OUTPUT FORMAT
            {{
            "action": "update_state",
            "args": {{
                "field_name": "extracted_value"
            }}
            }}

            If no new information is found, return:
            {{
            "action": "update_state",
            "args": {{}}
            }}

            ### INPUT DATA
            Question: {question}
            User message: {user_input}
            Current state: {current_state}
        """
      
    return ctx  

def valid_llm_response_guardrail(ctx: ExecContext) -> ExecContext:
        
        response = ctx.output
        
        if not response or not hasattr(response, 'content'):
                logger.error("Invalid LLM response structure")
                ctx.input = ctx.output
                ctx.output = None
                ctx.stop = True

        return ctx

def query_llm(ctx: ExecContext) -> ExecContext:
        """Query the LLM with a single attempt"""
        prompt = ctx.agent.prompt
        model = "llama3:latest"
        try:
            if not prompt or not isinstance(prompt, str):
                logger.error("Invalid prompt for LLM query")
                ctx.stop = True
                return ctx
            
            ollama = ChatOllama(
                model=model,
                base_url=os.getenv("OLLAMA_HOST"),
                temperature=0
            )
            
            response = ollama.invoke(prompt)
            ctx.output = response.content
            ctx.steps+=1
            # Should capture more data about token, latency, etc

            return ctx
            
            
        except Exception as e: # Should capture only Connectivity errors
            logger.error(f"LLM query error: {e}")
            ctx.stop = True
            return ctx

async def add_ia_message(ctx: ExecContext )-> ExecContext:
    if not ctx.session_id:
        ctx.error = "Not session_id set"
        ctx.stop = True
        return ctx
    memory = RedisMemory(session_id=ctx.session_id)
    msg, action = ctx.output
    res = await memory.add_ai_message(msg,action)

    if not res:
        ctx.error = "Error adding Message"
    if not res:
        ctx.error = "Error adding Message"
        
    return ctx

async def add_user_message(ctx: ExecContext )-> ExecContext:
    
    if not ctx.session_id:
        ctx.error = "Not session_id set"
        ctx.stop = True
        return ctx
    memory = RedisMemory(session_id=ctx.session_id)
    user_input = ctx.output
    res = await memory.add_user_message(user_input)

    if not res:
        ctx.error = "Error adding Message"
        
    return ctx

def parse_json(ctx: ExecContext) -> ExecContext: 

    
    if isinstance(ctx.output, str):

        res = json_parser(ctx.output)

        ctx.output = res
        
        if not res:
            ctx.stop = True
            ctx.error = "Error to parse LLM response"
    else:
        ctx.stop = True
        ctx.error = "parse_json step expect a string as input" 
            
    return ctx

async def router(ctx: ExecContext)-> ExecContext:
    pickup_time = ctx.state.get("pickup_time", None)
    
    
    if pickup_time == "immediate":
        # call service to send options
        print("mock service send options")
        ctx.stop = True
    elif all([
            ctx.state.get("pickup_location", None),
            ctx.state.get("destination", None),
            ctx.state.get("pickup_time", None),
            ctx.state.get("special_requests", None),
            ctx.state.get("confirmed", None)
        ]):
        await _schedule_booking(ctx.input, ctx.state)
        ctx.stop    
    else:
        ctx.jump_to = "ask_follow_up"
    
    return ctx

async def _schedule_booking(user_info, state) -> tuple[bool, str]:
        
        session_id, channel = user_info
        
        memory = RedisMemory(session_id)
        booking_state = RedisState(session_id)
        booking_service = BookingService()

        
        new_booking = await booking_service.create_booking(await booking_state.get_state(),user_info) 

        if new_booking:
            # Generate confirmation details
            confirmation_id = str(new_booking.identifier)
            
            
            message = f"""✅ Booking ID: {confirmation_id}
            A driver will contact you shortly with further details."""
        
            # Log the confirmation
            await memory.add_ai_message(message, "finalize_booking")

            return (True, message)
        
        return (False, "Error scheduling the booking")

async def _process_location(container: dict, field: str):
    location = container.get(field)

    # already processed
    if isinstance(location, dict) and set(location.keys()) == {"lat", "lon", "place"}:
        return

    # forward geocode if string
    if isinstance(location, str):
        res = await MapboxService().forward_geocode(location)
        if res:
            container[field] = json.dumps(res[0].__dict__)
        else:
            container.pop(field, None)

async def process_location(ctx: ExecContext) -> ExecContext:
        
        pickup = ctx.storage.get("delta_state", {}).get("pickup_location", None)
        dropoff = ctx.storage.get("delta_state", {}).get("destination", None)

        if pickup:
            await _process_location(ctx.storage.get("delta_state",{}), "pickup_location")

        if dropoff:
            await _process_location(ctx.storage, "destination")     

        return ctx

async def build_prompt_process_time(ctx:ExecContext) -> ExecContext:
      
        pickup_moment = ctx.storage.get("delta_state", {}).get("pickup_time", None)

        if pickup_moment:

            CURRENT_ISO_TIMESTAMP = datetime.now().isoformat(timespec='seconds')
            request = pickup_moment

            """
            Should return a JSON object { type: inmediate | schedule, target_time_iso: with the sifted time}
            """

            ctx.agent.prompt = f"""
                    
                    Current Time: {CURRENT_ISO_TIMESTAMP}

                    Analyze the user's pickup request.
                    Return a JSON object with:
                    1. "type": "immediate" or "scheduled"
                    - Anything request over 25 minutes of {CURRENT_ISO_TIMESTAMP} classify it as "scheduled"
                    2. "target_time_iso": If scheduled, output the exact target ISO timestamp. 
                    - You must handle the logic of "next day" if the time is earlier than the current time.
                    - Do not calculate the minute offset yourself. Just give the absolute time.

                    User: { request }
                    
                    """
        else:
            ctx.stop = True
        return ctx