# repositories/driver_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from db.models import Driver
from typing import Optional, Sequence
import logging

class DriverRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_top_available(self)-> Sequence[Driver]:
        try:
            async with self.db.begin():
                stmt = (
                    select(Driver)
                    .where(Driver.active == True)
                    .order_by(Driver.rank)
                    .with_for_update(skip_locked=True)  # skip rows locked by other transactions
                    .limit(300)
                )

                # Execute the query and get the result
                result = await self.db.execute(stmt)

                # If no drivers are available, return an empty list
                drivers = result.scalars().all()
                
                # Log the case where no drivers are found (optional)
                if not drivers:
                    logging.info("No active drivers found.")
                
                # Return the drivers (even if empty)
                return drivers
        
        except SQLAlchemyError as error:
            # Log SQLAlchemy errors (e.g., issues with the database connection or query)
            logging.exception(f"Error while fetching top available drivers: {error}")
            raise  # Re-raise the exception to propagate the error

        except Exception as error:
            # Log any other unexpected errors
            logging.exception(f"Unexpected error while fetching drivers: {error}")
            raise

    async def get_by_id(self, driver_id: int) -> Optional[Driver]:
        async with self.db.begin():
            result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
            return result.scalar_one_or_none()
    
    async def get_by_channel_id(self, driver_channel_id: int) -> Optional[Driver]:
        try:
            async with self.db.begin():
                result = await self.db.execute(select(Driver).where(Driver.channel_id == driver_channel_id))
                return result.scalar_one_or_none()
        except OperationalError as db_conn_error:
            logging.exception(f"Unexpected error while fetching drivers: {db_conn_error}")
            return None

        except Exception as error:
            # Log any other unexpected errors
            logging.exception(f"Unexpected error while fetching drivers: {error}")
            return None
        


    async def get_drivers_batch(self, last_id: int = 0, batch_size: int = 300):
        try:

            async with self.db.begin():
                stmt = (
                    select(Driver)
                    .where((Driver.active == True) & (Driver.id > last_id))
                    .with_for_update(skip_locked=True)  # skip rows locked by other transactions
                    .order_by(Driver.id.asc())
                    .limit(batch_size)
                )

                # Execute the query and get the result
                result = await self.db.execute(stmt)

                # If no drivers are available, return an empty list
                drivers = result.scalars().all()
                
                print(f"Choferes encontrados: {drivers}")

                # Log the case where no drivers are found (optional)
                if len(drivers) == 0:
                    logging.info("No active drivers found.")
                
                # Return the drivers (even if empty)
                return drivers
        
        except SQLAlchemyError as error:
            # Log SQLAlchemy errors (e.g., issues with the database connection or query)
            logging.exception(f"Error while fetching top available drivers: {error}")
            raise  # Re-raise the exception to propagate the error

        except Exception as error:
            # Log any other unexpected errors
            logging.exception(f"Unexpected error while fetching drivers: {error}")
            raise
        

    async def list_all(self) -> Sequence[Driver]:
        async with self.db.begin():
            result = await self.db.execute(select(Driver))
            return result.scalars().all()

    async def create(self, driver: Driver) -> Driver:
        try:
            async with self.db.begin():
                self.db.add(driver)
                return driver
        except Exception as error:
            # Log any other unexpected errors
            logging.exception(f"Unexpected error while fetching drivers: {error}")
            raise
        
    async def update_rank(self, driver_id: int, rank: int) -> Optional[Driver]:
        async with self.db.begin():
            driver = await self.get_by_id(driver_id)
            if driver:
                driver.rank = rank
            return driver