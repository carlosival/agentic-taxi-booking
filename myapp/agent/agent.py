import ast
import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from ._tool import Tool
from .tools import FinalizeBookingTool, UpdateBookingTool
from langchain_ollama import ChatOllama
from ._memory import RedisMemory
from ._state import RedisState
from services.booking_service import BookingService
from services.geolocation_service import MapboxService
from db.db import get_async_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Configuration with defaults
class AgentConfig:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        self.model_name = os.getenv("MODEL_NAME", "llama3")
        self.temperature = float(os.getenv("MODEL_TEMPERATURE", "0.0"))
        self.max_memory = int(os.getenv("MAX_MEMORY", "100"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        
        # Archival settings
        # self.enable_hybrid_memory = os.getenv("ENABLE_HYBRID_MEMORY", "true").lower() == "true"
        # self.archive_threshold_hours = int(os.getenv("ARCHIVE_THRESHOLD_HOURS", "24"))
        # self.auto_archive_on_completion = os.getenv("AUTO_ARCHIVE_ON_COMPLETION", "true").lower() == "true"
        
    def validate(self):
        """Validate configuration parameters"""
        if not self.ollama_host:
            raise ValueError("OLLAMA_HOST environment variable is required")
        if self.redis_port <= 0 or self.redis_port > 65535:
            raise ValueError("Invalid REDIS_PORT")
        if self.max_memory <= 0:
            raise ValueError("MAX_MEMORY must be positive")

class Agent:
    def __init__(self, session_id: Optional[str] = None, config: Optional[AgentConfig] = None, 
                 customer_channel_id: Optional[str] = None, customer_channel: str = "WHATSAPP"):
        self.config = config or AgentConfig()
        self.config.validate()
        
        self.session_id = session_id or self._generate_session_id() # Deprecate session the channel id
        self.customer_channel_id = customer_channel_id or self.session_id
        self.customer_channel = customer_channel
        self.tools = []
        
        # Initialize state and memory with error handling
        
        try:

            self.booking_state = RedisState(session_id=self.session_id)
            logger.info(f"Initialized RedisState for session {self.session_id}")

            self.memory = RedisMemory(session_id=self.session_id)
            logger.info(f"Initialized RedisMemory for session {self.session_id}")

                
        except Exception as e:
            logger.error(f"Failed to initialize Redis connections: {e}")
            raise RuntimeError(f"Agent initialization failed: {e}")
        
        logger.info(f"Agent initialized with session_id: {self.session_id}")
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID"""
        return f"session-{uuid.uuid4().hex[:8]}-{int(time.time())}"
    
    def _validate_session_id(self, session_id: str) -> bool:
        """Validate session ID format"""
        if not session_id or not isinstance(session_id, str):
            return False
        # Allow alphanumeric, hyphens, and underscores
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', session_id))


    def set_tools(self, tools: list) -> None:
        """Set the tools list"""
        if not isinstance(tools, list):
            raise ValueError("tools must be a list")
        self.tools = tools
        logger.info(f"Tools updated: {len(tools)} tools set")
    
    def set_memory(self, memory) -> None:
        """Set the memory instance"""
        self.memory = memory
        logger.info("Memory instance updated")
    
    def set_booking(self, booking) -> None:
        """Set the booking state instance"""
        self.booking_state = booking
        logger.info("Booking state instance updated")
    
    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the tools list"""
        self.tools.append(tool)
        logger.info(f"Tool added: {tool.__class__.__name__}")
    
    def set_session(self, session_id: str) -> bool:
        """Change the session ID and update state/memory accordingly"""
        if not self._validate_session_id(session_id):
            logger.error(f"Invalid session_id format: {session_id}")
            return False
        
        try:
            self.session_id = session_id
            self.booking_state.set_session(session_id)
            self.memory.set_session(session_id)
            logger.info(f"Session changed to: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to change session: {e}")
            return False


    def json_parser(self, json_str: str) -> Dict[str, Any]:
            """
            Try to parse a JSON string to Dict.
            If it fails, attempt to extract the first {...} block.
            If that also fails, try to parse it as a Python literal.
            """
            try:
                # First try: normal JSON parsing
                json_dict = json.loads(json_str)
                if isinstance(json_dict, dict):
                    return json_dict
                else:
                    raise ValueError("Top-level JSON is not an object")
            
            except json.JSONDecodeError:
                # Second try: extract first {...} using regex
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if match:
                    try:
                        json_dict = json.loads(match.group(0))
                        if isinstance(json_dict, dict):
                            return json_dict
                    except json.JSONDecodeError:
                        pass  # Continue to literal_eval fallback

                # Third try: attempt to parse as Python literal
                try:
                    python_dict = ast.literal_eval(json_str)
                    if isinstance(python_dict, dict):
                        # Convert to JSON-compatible: ensure keys are strings etc.
                        json_string = json.dumps(python_dict)
                        json_dict = json.loads(json_string)
                        return json_dict
                except (ValueError, SyntaxError):
                    pass

            # If everything fails, return a fallback
            logger.warning(f"JSON parsing failed for: {json_str[:100]}...")
            return {
                "action": "respond_to_user",
                "args": "I couldn't parse your response as valid information. Could you please rephrase?"
            }
            
    def json_parser1(self, input_string: str) -> Dict[str, Any]:
        """Alternative JSON parser using literal_eval"""
        try:
            python_dict = ast.literal_eval(input_string)
            json_string = json.dumps(python_dict)
            json_dict = json.loads(json_string)
            if isinstance(json_dict, dict):
                return json_dict
            raise ValueError("Invalid JSON response")
        except (ValueError, SyntaxError) as e:
            logger.warning(f"JSON parser1 failed: {e}")
            return {"action": "respond_to_user", "args": "I couldn't parse your response."}

    async def process_input(self, user_input: str, user_info: dict) -> str:
        """Process user input and return response"""
        try:

            user_id = user_info.get("user_id", "")
            user_channel = user_info.get("channel", None)

            # Validate inputs
            if not user_input or not isinstance(user_input, str):
                return "Please provide a valid message."
            
            """ if not self._validate_session_id(user_id):
                return "Invalid session. Please start a new conversation." """
            
            # Sanitize input
            user_input = self._sanitize_input(user_input)
            
            # Set session for this request
            if not self.set_session(user_id):
                return "Unable to process your request. Please try again."
            
            # Update booking information
            update_success = await self.gather_update_info(user_input, user_id)
            if not update_success:
                return "I had trouble processing your message. Could you please rephrase?"

            # Check if booking is confirmed
            if await self.is_confirm():
                return await self.finalize_booking(user_info)

            return await self.ask_follow(user_id)
            
        except Exception as e:
            logger.error(f"Error processing input: {e}")
            return "I'm sorry, I encountered an error. Let's start over."
    
    def _sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to prevent injection attacks"""
        # Remove potential harmful characters while preserving normal punctuation
        sanitized = re.sub(r'[<>"\\]', '', user_input)
        # Limit input length
        return sanitized[:1000] if len(sanitized) > 1000 else sanitized


    async def finalize_booking(self, user_info: dict) -> str:
        
        user_id = None
        """Finalize the booking and return confirmation message"""
        try:
            
            
            user_id = user_info.get("user_id", "")
            channel = user_info.get("channel")

            # Validate booking state before finalizing
            if not await self.is_complete():
                logger.warning(f"Attempted to finalize incomplete booking for {user_id}")
                return "Booking cannot be completed. Some information is missing."
            
              
            # Auto-archive conversation implement later
            
            booking_service = BookingService()

            new_booking = await booking_service.create_booking(await self.booking_state.get_state(),user_info) 

            if new_booking:
                # Generate confirmation details
                confirmation_id = str(new_booking.identifier)
                  
                
                message = f"""✅ Booking ID: {confirmation_id}
                A driver will contact you shortly with further details."""

                # Log the confirmation
                if not await self.memory.add_ai_message(message, "finalize_booking"):
                    logger.warning(f"Failed to save confirmation message for {user_id}")
                
                # Before clear pass memory to a long memory support postgres table or blog file
                # Auto-archive conversation implement later
                
                await self.booking_state.clear()
                await self.memory.clear()
                
                logger.info(f"Booking finalized for {user_id}, confirmation: {confirmation_id}")
                return message
            
            return "Sorry, there was an error finalizing your booking. Please try again."

        except Exception as e:
            logger.error(f"Error finalizing booking for {user_id}: {e}")
            return "Sorry, there was an error finalizing your booking. Please try again."

    async def gather_update_info(self, user_input: str, user_id: str) -> bool:
        """Gather and update booking information from user input"""
        try:

            # Get conversation history
            all_messages = await self.memory.get_messages(limit=self.config.max_memory)
            if all_messages is None:
                logger.error(f"Failed to retrieve messages for {user_id}")
                return False

            # Get last system question if any
            question = ""
            for msg in reversed(all_messages):
                if msg.get("role") == "ai" and msg.get("action") == "respond_to_user":
                    question = msg.get("content", "")
                    break
            
            logger.debug(f"Previous system question: {question}")
            
            # Add user message to memory
            if not await self.memory.add_user_message(user_input):
                logger.error(f"Failed to save user message for {user_id}")
                return False
            
            # Build context for LLM
            context = self._build_context(all_messages)
            logger.debug(f"Context length: {len(context)} characters")
        
            # Build prompt for information extraction
            current_state = await self.booking_state.get_state()
            if not current_state:
                logger.error(f"Failed to get current booking state for {user_id}")
                return False
            
            prompt = f"""
        You are a helpful and precise taxi booking assistant.
        Read the system's question and the user's message carefully.
        Extract **only** the booking fields you can confidently identify from the user's message.
        **Never guess or add missing information.**
        Include **only** fields actually present in the message.

        💬 Language:
        - Detect and use the language the user prefers (e.g., English, Spanish).
        - Always speak in simple, polite, and natural language.

        Question:
        {question}

        User message:
        {user_input}

        Current booking state (JSON):
        {json.dumps(current_state.model_dump(exclude_unset=False))}

        📏 Response Rules:
        - Respond with **exactly one valid JSON object** in this format (REQUIRED):
        {{
        "action": "update_state",
        "args": {{
            "pickup_location": "...",
            "destination": "...",
            "pickup_time": "...",
            "special_requests": "...",
            "confirmed": true/false
        }}
        }}

        - args must be strict valid JSON that can be parsed by the BookingState Pydantic model.
        - Include only the fields you extracted** — omit any you cannot identify with certainty. 
        - For `special_requests`:  
            - Include `special_requests` if the user clearly describes a request.  
            - Do **not** accept vague answers like “you know”, “as usual”, or “same as last time”.
            - If the user don't have a clearly special request then set `special_requests` to "N/A".
        - For `confirmed`:
            - Only extract `confirmed` if the user clearly says **"yes" or "no"** in response to a confirmation question.
            - Vague replies like “okay”, “sure”, “alright”, or “thank you” **must not be treated as confirmation**.
        - *DO NOT** add explanations, notes, or extra text outside the JSON object.

        
        If no valid information can be extracted:
        - Respond with **exactly one valid JSON object** in this format (**REQUIRED**)

        {{
        "action": "update_state",
        "args": {{}}
        }}
        
        
        Return only the JSON object. Nothing else.

    """

            
            # Query LLM with retry logic
            response = self._query_llm_with_retry(prompt)
            if not response:
                logger.error(f"LLM query failed for {user_id}")
                return False
            
            logger.debug(f"LLM update response: {response[:200]}...")
            
            # Parse response
            response_dict = self.json_parser(response)
            if not response_dict or "args" not in response_dict:
                logger.error(f"Invalid LLM response format for {user_id}")
                return False
            
            args = response_dict["args"]
            if not isinstance(args, dict):
                logger.error(f"Invalid args type: {type(args)}")
                return False
            


            # Update booking state
            update_success = await self.booking_state.update(args)
            if not update_success:
                logger.warning(f"Failed to update booking state for {user_id}")
            
            # Save AI response to memory
            if not await self.memory.add_ai_message(str(response_dict["args"]), response_dict.get("action", "update_state")):
                logger.warning(f"Failed to save AI message for {user_id}")
            
            current_state = await self.booking_state.get_state()
            logger.info(f"Booking state updated for {user_id}: {current_state.model_dump()}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in gather_update_info for {user_id}: {e}")
            return False
    
    def _build_context(self, messages: list) -> str:
        """Build conversation context from messages"""
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

    async def is_confirm(self) -> bool:
        """Check if booking is confirmed"""
        try:
            return await self.booking_state.is_confirm()
        except Exception as e:
            logger.error(f"Error checking confirmation status: {e}")
            return False

    async def is_complete(self) -> bool:
        """Check if booking is complete"""
        try:
            return await self.booking_state.is_complete()
        except Exception as e:
            logger.error(f"Error checking completion status: {e}")
            return False
    
    async def get_booking_summary(self) -> str:
        """Get a summary of the current booking state"""
        try:
            return await self.booking_state.summary()
        except Exception as e:
            logger.error(f"Error getting booking summary: {e}")
            return "Unable to retrieve booking details."
    
    def reset_booking(self) -> bool:
        """Reset the current booking state"""
        try:
            # Create a new booking state
            self.booking_state = RedisState(
                session_id=self.session_id,
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db
            )
            logger.info(f"Booking state reset for session: {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"Error resetting booking state: {e}")
            return False
    
    async def ask_follow(self, user_id: str) -> str:
        """Ask follow-up questions to complete the booking"""
        try:
            # Get conversation history
            all_messages = await self.memory.get_messages(limit=self.config.max_memory)
            if all_messages is None:
                logger.error(f"Failed to retrieve messages for follow-up: {user_id}")
                return "I'm having trouble accessing our conversation. Could you please repeat your request?"
            
            context = self._build_context(all_messages)
        
            # Build prompt for follow-up questions
            current_state = await self.booking_state.get_state()
            if not current_state:
                logger.error(f"Failed to get current booking state for follow-up: {user_id}")
                return "I'm having trouble accessing your booking information. Let's start over."
            
            prompt = f"""
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
        {json.dumps(current_state.model_dump(exclude_unset=False))}

        Your task:
        - Review the current booking state and the conversation context below.
        - Identify the **next missing detail**, in this order:
        1. pickup_location
        2. destination
        3. pickup_time
        4. passengers
        5. special_requests
        6. confirmed

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


            # Query LLM with retry logic
            response = self._query_llm_with_retry(prompt)
            if not response:
                return "I'm having trouble generating a response. Please try again."
            
            logger.debug(f"LLM follow-up response: {response[:200]}...")
            
            # Parse response
            response_dict = self.json_parser(response)
            if not response_dict or "args" not in response_dict:
                logger.error(f"Invalid LLM response format for follow-up: {user_id}")
                return "Let me ask you again - could you please provide more details?"
            
            # Save AI response to memory
            if not await self.memory.add_ai_message(response_dict["args"], response_dict.get("action", "respond_to_user")):
                logger.warning(f"Failed to save AI follow-up message for {user_id}")
            
            return response_dict["args"]
            
        except Exception as e:
            logger.error(f"Error in ask_follow for {user_id}: {e}")
            return "I'm having trouble processing your request. Could you please try again?"
         


    def query_llm(self, prompt: str) -> Any:
        """Query the LLM with a single attempt"""
        try:
            if not prompt or not isinstance(prompt, str):
                logger.error("Invalid prompt for LLM query")
                return None
            
            ollama = ChatOllama(
                model=self.config.model_name,
                base_url=self.config.ollama_host,
                temperature=self.config.temperature
            )
            
            response = ollama.invoke(prompt)
            if not response or not hasattr(response, 'content'):
                logger.error("Invalid LLM response structure")
                return None
            
            return response.content # Should return a string with JSON format
            
        except Exception as e:
            logger.error(f"LLM query error: {e}")
            return None
    
    def _query_llm_with_retry(self, prompt: str) -> Optional[str]:
        """Query LLM with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                response = self.query_llm(prompt)
                if response:
                    return response
                logger.warning(f"LLM query attempt {attempt + 1} returned empty response")
            except Exception as e:
                logger.warning(f"LLM query attempt {attempt + 1} failed: {e}")
            
            if attempt < self.config.max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
        
        logger.error(f"All {self.config.max_retries} LLM query attempts failed")
        return None
    
    async def _process_pickup(self, args):

        if "pickup_location" in args:
            if isinstance(args["pickup_location"], dict) and args["pickup_location"].keys == {"lan", "lon", "place"}:
                return

            if type(args["pickup_location"]) == "str":
                res = await MapboxService().forward_geocode(args["pickup_location"])
                if len(res) > 0: 
                    args["pickup_location"] = json.dumps(res[0].__dict__)
                else:
                    del args["pickup_location"]

    async def _process_dropoff(self, args): 
            if isinstance(args["destination"], dict) and args["destination"].keys == {"lan", "lon", "place"}:
                return

            if type(args["destination"]) == "str":
                res = await MapboxService().forward_geocode(args["destination"])
                if len(res) > 0: 
                    args["destination"] = res[0].model_dump()
                else:
                    del args["destination"]
    
    async def _process_time(self, args):  

        if  "pickup_time" in args :

            CURRENT_ISO_TIMESTAMP = datetime.now().isoformat(timespec='seconds')
            request = args["pickup_time"]

            """
            Should return a JSON object { type: inmediate | schedule, target_time_iso: with the sifted time}
            """

            prompt=f"""
                    
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


            # Query LLM with retry logic
            response = self.query_llm(prompt)
            if not response:
                logger.error(f"LLM query failed for proccess pickup time")
            
            
            # Parse response
            response_dict = self.json_parser(response)

            # Validate the format with keys type and target_time_iso

            args["pickup_time"] = json.dumps(response_dict)


    async def run(self, user_id: Optional[str] = None) -> None:

        async def async_input(prompt: str) -> str:
            """Async version of input using asyncio.to_thread"""
            user_input = await asyncio.to_thread(input, prompt)
            return user_input.strip()

        """Run the agent in interactive mode"""
        try:
            session_user = user_id or f"user-{int(time.time())}"
            logger.info(f"Starting interactive session for {session_user}")
            
            print("Agent: Hello! How can I assist you with your taxi booking today?")
            
            while not (await self.is_confirm() and await self.is_complete()):
                try:
                    # Use async_input for non-blocking input
                    user_input = await async_input("You: ")
                    
                    # Check for exit commands
                    if user_input.lower() in ["exit", "bye", "quit", "close"]:
                        print("Agent: Thank you for using our service. Goodbye!")
                        break
                    
                    # Skip empty inputs
                    if not user_input:
                        print("Agent: Please tell me how I can help you.")
                        continue
                    
                    # Process user input
                    response = await self.process_input(user_input, {"channel":"TELEGRAM","user_id":session_user})
                    print(f"Agent: {response}")
                    
                    # Check if booking is confirmed and complete
                    if await self.is_confirm() and await self.is_complete():
                        print("Agent: Your booking is complete!. Thank you Goodbye?")
                    
                except KeyboardInterrupt:
                    print("\nAgent: Session interrupted. Goodbye!")
                    break
                except Exception as e:
                    logger.error(f"Error in interactive loop: {e}")
                    print("Agent: I encountered an error. Let's continue...")

            print("End of script")        
        except Exception as e:
            logger.error(f"Fatal error in run method: {e}")
            print("Agent: I'm sorry, I encountered a fatal error and need to restart.")

if __name__ == "__main__":
    try:
        # Initialize with configuration
        config = AgentConfig()
        agent = Agent(config=config)
        asyncio.run(agent.run()) 
    except Exception as e:
        logger.error(f"Failed to start agent: {e}")
        print(f"Error: {e}")

