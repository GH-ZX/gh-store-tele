# ADR-010: Keep fiat wallet despite Telegram Stars policy for digital goods

- **Status:** Accepted (documented decision, no code change)
- **Date:** 2026-09-13
- **Context anchor:** audit item 10; wallet routes in `routes/tma_wallet.py` (external funding rails)
  alongside in-bot digital purchases.

## Context

Telegram's payment policy requires bots to use **Stars** (or approved payment
providers) to sell **digital goods delivered inside Telegram**
(https://core.telegram.org/bots/payments-stars). GH Store sells digital
credentials/activations inside chat and the Mini App, while the wallet
(`top_up_amount` / `consume_records`) is funded through external rails
(SAM / crypto forwarding / Stars) exposed at `routes/tma_wallet.py:90`.

This creates a policy risk: in-bot digital sales settled against a fiat wallet
rather than Stars.

## Options considered

1. **Drop the fiat wallet; force Stars for all in-bot digital sales.**
   Correct on policy but (a) a large share of users/countries fund via methods
   Stars does not reach (SAM/SYP, crypto), (b) the reseller program and
   activation-renews depend on pre-funded wallet accounting, (c) a hard switch
   would break checkout for existing balances.
2. **Keep the wallet + external funding** (chosen).
3. Hybrid (Stars only for chat-delivered goods): adds two parallel payment
   paths and a much larger migration for marginal compliance value today.

## Decision

**Keep the fiat wallet and its external funding rails.** Telegram Stars remains
supported as one of the funding options (`GHSTORE_STARS_ENABLED`). Consumers pay
from wallet balance; wallet is replenished by clearly-labeled external funding.

Accepted business risk: platform enforcement for chat-delivered digital goods
settled via non-Stars rails. Mitigations currently in place / planned:

- Stars is offered as a payment rail (`handlers/user/stars.py`, `routes/tma_wallet.py`).
- All funding rails are externally disclosed and user-initiated.
- `handlers/user/stars.py` already routes Stars-funded purchases through the
  external-payment flow (`externally_paid`, `order_cost`) rather than wallet debit.

## Consequences

- No change to wallet/checkout code required for this item.
- If Telegram enforcement escalates, the lowest-cost fallback is to route
  chat-delivered goods through a Stars-only checkout (keeps coexist with
  wallet funding for the rest).
- This ADR documents that the drift from the "Stars-only for in-Telegram
  digital goods" guidance is a deliberate, recorded business decision.