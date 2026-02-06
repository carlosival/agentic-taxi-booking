import logging
import inspect
from typing import Callable, List, Dict, Optional, Any, AsyncGenerator, Awaitable
from yaafpy.adapters import normalize_step_result
from yaafpy.types import ExecContext

logger = logging.getLogger("yaaf.workflow")

class Workflow:
    def __init__(self):
        self._middleware: List[Callable[[ExecContext], Awaitable[ExecContext]]] = []
        self._registry: Dict[str, int] = {}

    def use(self, middleware: Callable[[ExecContext], Awaitable[ExecContext]], name: Optional[str] = None):
        self._middleware.append(middleware)
        if name:
            self._registry[name] = len(self._middleware) - 1
        else:
            self._registry[middleware.__name__] = len(self._middleware) - 1    
        return self


    async def run_stream(self, ctx: Optional[ExecContext] = None) -> ExecContext:

            if ctx and ctx.jump_to and self._registry.get(ctx.jump_to) is None:
                raise ValueError("Jump target is not valid")

            exec_ctx = ctx or ExecContext(_workflow=self)

            if exec_ctx.stop:
                return exec_ctx

            cursor = self._registry.get(exec_ctx.jump_to, 0) if exec_ctx.jump_to else 0
            n = len(self._middleware)

            while cursor < n:
                step = self._middleware[cursor]

                try:
                    copy_ctx = exec_ctx.model_copy(deep=True)
                    copy_ctx._workflow = self

                    result = step(copy_ctx)

                    async for new_ctx in normalize_step_result(result):

                        if new_ctx is None:
                            raise ValueError("Middleware returned None")

                        exec_ctx = new_ctx

                        if exec_ctx.stop:
                            return exec_ctx

                        if exec_ctx.jump_to:
                            if exec_ctx.jump_to not in self._registry:
                                raise ValueError(f"Jump target {exec_ctx.jump_to} not found")
                            cursor = self._registry[exec_ctx.jump_to]
                            exec_ctx.jump_to = None
                            break  # break inner async-for → continue outer while

                        else:
                            cursor += 1  # normal progression

                except Exception as e:
                    logger.error(f"[Workflow Error] Step index {cursor} failed: {e}")
                    exec_ctx.stop = True
                    return exec_ctx

            return exec_ctx


    async def run(self, ctx: Optional[ExecContext] = None) -> ExecContext:
    
        if ctx and ctx.jump_to and self._registry.get(ctx.jump_to) is None: 
            raise ValueError("Jump target is not valid")  

        if ctx is None:
            exec_ctx = ExecContext(workflow=self)
        else:
            exec_ctx = ctx
        
        if ctx.stop:
            return ctx
        
        if ctx.jump_to is None:
            cursor = 0
        else:
            cursor = self._registry[ctx.jump_to]

        n = len(self._middleware)

        while cursor < n:
            try:
                # Force functional approach: 
                # Pass a COPY of the context so middleware cannot mutate the loop's reference in-place
                
                copy_ctx = exec_ctx.model_copy(deep=True)
                copy_ctx.workflow = self # Keep the workflow reference because it is lost during copy
                result = self._middleware[cursor](copy_ctx)
                
                if inspect.isawaitable(result):
                   exec_ctx = await result
                else:
                   exec_ctx = result
                
                if exec_ctx is None:
                    raise ValueError("Middleware returned None")

                if exec_ctx.stop:
                    return exec_ctx

                if exec_ctx.jump_to and self._registry.get(exec_ctx.jump_to) is None:
                    raise ValueError(f"Jump target {exec_ctx.jump_to} not found in registry")

                if exec_ctx.jump_to:
                    cursor = self._registry[exec_ctx.jump_to]
                    exec_ctx.jump_to = None
                else:
                    cursor +=1 
            
            except Exception as e:
                logger.error(f"[Workflow Error] Step index {cursor} failed: {e}")
                exec_ctx.stop = True
                return exec_ctx 
            
        return exec_ctx 
            

