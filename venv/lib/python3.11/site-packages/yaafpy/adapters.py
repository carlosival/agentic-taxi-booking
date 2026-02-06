import logging
from typing import Callable, Optional, Awaitable
from yaafpy.types import ExecContext
import inspect
from typing import AsyncIterator, Any

logger = logging.getLogger("yaaf.funcs")



async def normalize_step_result(result) -> AsyncIterator[Any]:
    # Case 1: async generator
    if inspect.isasyncgen(result):
        async for item in result:
            yield item
        return

    # Case 2: awaitable (async function)
    if inspect.isawaitable(result):
        value = await result
        yield value
        return

    # Case 3: sync generator (optional but powerful)
    if inspect.isgenerator(result):
        for item in result:
            yield item
        return

    # Case 4: normal value
    yield result


def as_middleware_stream(workflow: "Workflow", ctx: Optional[ExecContext] = None) -> Callable[[ExecContext], Awaitable[ExecContext]]:
    async def middleware(ctx: ExecContext):
        async for out_ctx in workflow.run_stream(ctx):
            yield out_ctx
    return middleware


def as_middleware(workflow: "Workflow", ctx: Optional[ExecContext] = None) -> Callable[[ExecContext], Awaitable[ExecContext]]:
    """
    Wraps a Workflow object as a middleware function.
    
    Args:
        workflow: The child workflow to execute.
        exec_ctx: Optional execution context to override/interject (currently unused by default logic).
    Returns:
        A middleware function compatible with the workflow engine.
    """
    async def wrapped_step(ctx: ExecContext) -> ExecContext:
        # We pass the current context to the child workflow.
        # The child workflow.run() method will clone it internally,
        # execute its steps, and return the modified context.
        # We then return that modified context to the parent workflow,
        # ensuring state changes propagate.
        
        # Note: If exec_ctx was provided at registration, one might expect it to be used.
        # However, middleware typically acts on the flow's context.
        # We will use the runtime `ctx` to maintain continuity.
        
        logger.info(f"[Trace] Entering nested workflow with input: {ctx.input}")

        try:
            result_ctx = await workflow.run(ctx)
            logger.info(f"[Trace] Exiting nested workflow. Output: {result_ctx.output}")
            return result_ctx
        except Exception as e:
            logger.error(f"[Trace] Nested workflow failed: {e}")
            raise e

    return wrapped_step
