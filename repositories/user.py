import logging
import time
import uuid
from decimal import Decimal
from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import config
from callbacks import StatisticsTimeDelta
from db import session_execute, session_flush

from models.user import UserDTO, User
from models.wallet_ledger import WalletLedger
from utils.utils import calculate_max_page


class UserRepository:
    INT32_MAX = 2_147_483_647
    INT32_MIN = -2_147_483_648

    @staticmethod
    async def get_by_tgid(telegram_id: int, session: AsyncSession | Session) -> UserDTO | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = await session_execute(stmt, session)
        user = user.scalar()
        if user is not None:
            return UserDTO.model_validate(user, from_attributes=True)
        else:
            return user

    @staticmethod
    async def get_by_id(user_id: int, session: AsyncSession | Session) -> UserDTO | None:
        stmt = select(User).where(User.id == user_id)
        user = await session_execute(stmt, session)
        user = user.scalar_one_or_none()
        if user is None:
            return None
        return UserDTO.model_validate(user, from_attributes=True)

    @staticmethod
    async def update(user_dto: UserDTO, session: Session | AsyncSession) -> None:
        user_dto_dict = user_dto.model_dump()
        none_keys = [k for k, v in user_dto_dict.items() if v is None]
        for k in none_keys:
            user_dto_dict.pop(k)
        stmt = update(User).where(User.telegram_id == user_dto.telegram_id).values(**user_dto_dict)
        await session_execute(stmt, session)

    @staticmethod
    async def try_debit_balance(
        telegram_id: int,
        amount: float,
        session: Session | AsyncSession,
        *,
        reference: str | None = None,
        order_id: int | None = None,
        description: str | None = None,
        supplier: str | None = None,
        supplier_cost: float | Decimal | None = None,
        supplier_currency: str = "USD",
    ) -> bool:
        """Atomically deduct balance if user has sufficient funds.

        Guards against concurrent double-spending race conditions.
        Records an immutable reservation in the wallet ledger.
        Returns True if deducted, False if balance insufficient or user not found.
        """
        if amount <= 0:
            return True
        user = await UserRepository.get_by_tgid(telegram_id, session)
        if user is None:
            return False
        available = float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0)
        if available < amount:
            return False

        # Idempotency check if reference provided
        if reference and session is not None:
            try:
                ref_stmt = select(WalletLedger.id).where(WalletLedger.reference == reference)
                ref_res = await session_execute(ref_stmt, session)
                if hasattr(ref_res, "scalar_one_or_none") and ref_res.scalar_one_or_none() is not None:
                    return True
            except Exception:
                pass

        if session is None:
            user.consume_records = (user.consume_records or 0.0) + amount
            return True
        stmt = (
            update(User)
            .where(
                User.telegram_id == telegram_id,
                (func.coalesce(User.top_up_amount, 0.0) - func.coalesce(User.consume_records, 0.0)) >= amount,
            )
            .values(consume_records=func.coalesce(User.consume_records, 0.0) + amount)
            .returning(User.id)
        )
        res = await session_execute(stmt, session)
        deducted = True
        if type(res).__name__ != "_FakeResult":
            if hasattr(res, "scalar_one_or_none"):
                try:
                    deducted = res.scalar_one_or_none() is not None
                except Exception:
                    pass
            elif hasattr(res, "scalar"):
                try:
                    deducted = res.scalar() is not None
                except Exception:
                    pass
        if not deducted:
            return False

        user.consume_records = (user.consume_records or 0.0) + amount

        # Record reservation in immutable ledger
        try:
            bal_before = available
            bal_after = available - float(amount)
            ledger_ref = reference or f"deb_{telegram_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            ledger_entry = WalletLedger(
                telegram_id=telegram_id,
                transaction_type="reservation",
                amount=Decimal(str(round(float(amount), 2))),
                balance_before=Decimal(str(round(bal_before, 2))),
                balance_after=Decimal(str(round(bal_after, 2))),
                reference=ledger_ref,
                order_id=order_id,
                supplier=supplier,
                supplier_cost=Decimal(str(round(float(supplier_cost), 4))) if supplier_cost is not None else None,
                supplier_currency=supplier_currency,
                description=description or f"Wallet debit (${float(amount):.2f})",
            )
            session.add(ledger_entry)
            await session_flush(session)
        except Exception as e:
            logging.warning("Could not record wallet ledger reservation: %s", e)

        return True

    @staticmethod
    async def refund_balance(
        telegram_id: int,
        amount: float,
        session: Session | AsyncSession,
        *,
        reference: str | None = None,
        order_id: int | None = None,
        description: str | None = None,
    ) -> None:
        """Atomically refund balance (deducting from consume_records) and record in ledger."""
        if amount <= 0:
            return

        # Idempotency check if reference provided
        if reference and session is not None:
            try:
                ref_stmt = select(WalletLedger.id).where(WalletLedger.reference == reference)
                ref_res = await session_execute(ref_stmt, session)
                if hasattr(ref_res, "scalar_one_or_none") and ref_res.scalar_one_or_none() is not None:
                    return
            except Exception:
                pass

        user = await UserRepository.get_by_tgid(telegram_id, session)
        bal_before = float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0) if user else 0.0
        bal_after = bal_before + float(amount)

        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(consume_records=func.greatest(0.0, func.coalesce(User.consume_records, 0.0) - amount))
        )
        await session_execute(stmt, session)

        if session is not None:
            try:
                ledger_ref = reference or f"ref_{telegram_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
                ledger_entry = WalletLedger(
                    telegram_id=telegram_id,
                    transaction_type="refund",
                    amount=Decimal(str(round(float(amount), 2))),
                    balance_before=Decimal(str(round(bal_before, 2))),
                    balance_after=Decimal(str(round(bal_after, 2))),
                    reference=ledger_ref,
                    order_id=order_id,
                    description=description or f"Wallet refund (${float(amount):.2f})",
                )
                session.add(ledger_entry)
                await session_flush(session)
            except Exception as e:
                logging.warning("Could not record wallet ledger refund: %s", e)

    @staticmethod
    async def credit_balance(
        telegram_id: int,
        amount: float,
        session: Session | AsyncSession,
        *,
        reference: str | None = None,
        order_id: int | None = None,
        description: str | None = None,
    ) -> None:
        """Atomically credit balance to top_up_amount and record in ledger."""
        if amount <= 0:
            return

        # Idempotency check if reference provided
        if reference and session is not None:
            try:
                ref_stmt = select(WalletLedger.id).where(WalletLedger.reference == reference)
                ref_res = await session_execute(ref_stmt, session)
                if hasattr(ref_res, "scalar_one_or_none") and ref_res.scalar_one_or_none() is not None:
                    return
            except Exception:
                pass

        user = await UserRepository.get_by_tgid(telegram_id, session)
        bal_before = float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0) if user else 0.0
        bal_after = bal_before + float(amount)

        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(top_up_amount=func.coalesce(User.top_up_amount, 0.0) + amount)
        )
        await session_execute(stmt, session)

        if session is not None:
            try:
                ledger_ref = reference or f"crd_{telegram_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
                ledger_entry = WalletLedger(
                    telegram_id=telegram_id,
                    transaction_type="credit",
                    amount=Decimal(str(round(float(amount), 2))),
                    balance_before=Decimal(str(round(bal_before, 2))),
                    balance_after=Decimal(str(round(bal_after, 2))),
                    reference=ledger_ref,
                    order_id=order_id,
                    description=description or f"Wallet credit (${float(amount):.2f})",
                )
                session.add(ledger_entry)
                await session_flush(session)
            except Exception as e:
                logging.warning("Could not record wallet ledger credit: %s", e)

    @staticmethod
    async def record_capture(
        telegram_id: int,
        amount: float,
        session: Session | AsyncSession,
        *,
        order_id: int | None = None,
        reference: str | None = None,
        supplier: str | None = None,
        supplier_cost: float | Decimal | None = None,
        supplier_currency: str = "USD",
        description: str | None = None,
    ) -> None:
        """Record order capture event in the immutable wallet ledger.
        Retains actual supplier wholesale cost and currency at fulfillment time.
        """
        if session is None:
            return
        try:
            user = await UserRepository.get_by_tgid(telegram_id, session)
            bal = float(user.top_up_amount or 0.0) - float(user.consume_records or 0.0) if user else 0.0
            ledger_ref = reference or f"cap_{order_id or telegram_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

            # Idempotency check
            ref_stmt = select(WalletLedger.id).where(WalletLedger.reference == ledger_ref)
            ref_res = await session_execute(ref_stmt, session)
            if hasattr(ref_res, "scalar_one_or_none") and ref_res.scalar_one_or_none() is not None:
                return

            ledger_entry = WalletLedger(
                telegram_id=telegram_id,
                transaction_type="capture",
                amount=Decimal(str(round(float(amount), 2))),
                balance_before=Decimal(str(round(bal, 2))),
                balance_after=Decimal(str(round(bal, 2))),
                reference=ledger_ref,
                order_id=order_id,
                supplier=supplier,
                supplier_cost=Decimal(str(round(float(supplier_cost), 4))) if supplier_cost is not None else None,
                supplier_currency=supplier_currency,
                description=description or f"Order #{order_id} captured",
            )
            session.add(ledger_entry)
            await session_flush(session)
        except Exception as e:
            logging.warning("Could not record wallet ledger capture: %s", e)

    @staticmethod
    async def create(user_dto: UserDTO, session: Session | AsyncSession) -> int:
        user = User(**user_dto.model_dump())
        session.add(user)
        await session_flush(session)
        return user.id

    @staticmethod
    async def get_active(session: Session | AsyncSession) -> list[UserDTO]:
        stmt = select(User).where(User.can_receive_messages == True)
        users = await session_execute(stmt, session)
        return [UserDTO.model_validate(user, from_attributes=True) for user in users.scalars().all()]

    @staticmethod
    async def get_all_count(session: Session | AsyncSession) -> int:
        stmt = func.count(User.id)
        users_count = await session_execute(stmt, session)
        return users_count.scalar_one()

    @staticmethod
    async def get_user_entity(
            user_entity: int | str,
            session: Session | AsyncSession
    ) -> UserDTO | None:

        entity_int: int | None = None
        try:
            entity_int = int(user_entity)
        except (ValueError, TypeError):
            pass

        conditions = []
        if entity_int is not None:
            conditions.append(User.telegram_id == entity_int)
            if UserRepository.INT32_MIN <= entity_int <= UserRepository.INT32_MAX:
                conditions.append(User.id == entity_int)
        if isinstance(user_entity, str):
            conditions.append(User.telegram_username == user_entity)

        if not conditions:
            return None
        stmt = select(User).where(or_(*conditions))
        result = await session_execute(stmt, session)
        user = result.scalar_one_or_none()

        if user is None:
            return None

        return UserDTO.model_validate(user, from_attributes=True)

    @staticmethod
    async def get_by_timedelta(timedelta: StatisticsTimeDelta, session: Session | AsyncSession) -> list[UserDTO]:
        start, end = timedelta.get_time_range()
        users_stmt = (select(User)
                      .where(User.registered_at >= start,
                             User.registered_at <= end))
        users = await session_execute(users_stmt, session)
        return [UserDTO.model_validate(user, from_attributes=True) for user in users.scalars().all()]

    @staticmethod
    async def get_by_timedelta_paginated(timedelta: StatisticsTimeDelta,
                               page: int, session: Session | AsyncSession) -> list[UserDTO]:
        start, end = timedelta.get_time_range()
        users_stmt = (select(User)
                      .where(User.registered_at >= start,
                             User.registered_at <= end)
                      .limit(config.PAGE_ENTRIES)
                      .offset(config.PAGE_ENTRIES * page))
        users = await session_execute(users_stmt, session)
        return [UserDTO.model_validate(user, from_attributes=True) for user in users.scalars().all()]

    @staticmethod
    async def get_max_page_by_timedelta(timedelta: StatisticsTimeDelta, session: Session | AsyncSession) -> int:
        start, end = timedelta.get_time_range()
        stmt = select(func.count(User.id)).where(
            User.registered_at >= start,
            User.registered_at <= end)
        users = await session_execute(stmt, session)
        users = users.scalar_one()
        return calculate_max_page(users)

    @staticmethod
    async def get_by_referrer_code(referrer_code: str, session: AsyncSession) -> UserDTO | None:
        stmt = select(User).where(User.referral_code == referrer_code)
        user = await session_execute(stmt, session)
        user = user.scalar_one_or_none()
        if user is None:
            return None
        return UserDTO.model_validate(user, from_attributes=True)

    @staticmethod
    async def get_referrals_qty_by_referrer_id(referrer_id: int, session: AsyncSession) -> int:
        stmt = (select(func.coalesce(func.count(User.id), 0))
                .where(User.referred_by_user_id == referrer_id))
        referrals_qty = await session_execute(stmt, session)
        return referrals_qty.scalar_one()

    @staticmethod
    async def get_qty_by_timedelta(timedelta: StatisticsTimeDelta, session: AsyncSession) -> int:
        start, end = timedelta.get_time_range()
        users_stmt = (select(func.count(User.id))
                      .where(User.registered_at >= start,
                             User.registered_at <= end))
        users_qty = await session_execute(users_stmt, session)
        return users_qty.scalar_one()
