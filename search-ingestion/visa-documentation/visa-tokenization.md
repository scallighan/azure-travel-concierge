# Visa Intelligent Commerce (VIC) — Payment Tokenization Overview (Demo Data)

> Synthetic demo content describing, at a high level, how the mock Visa MCP
> server in this sample models payment tokenization. It does not reflect the real
> Visa APIs.

## What is tokenization?

Tokenization replaces a card's Primary Account Number (PAN) with a
**network token** (a "provisioned token"). The token can be used for future
purchases without exposing the real card number. If a merchant is breached, the
token is useless outside its bound context.

## Card onboarding flow

1. The user enters card details into a **secure iframe** — card data goes
   directly to the payment network, never to the merchant's servers.
2. The network **enrolls** the card and returns a `vProvisionedTokenId`.
3. The merchant stores only the token id plus the **last four digits** and brand.
   The PAN and CVV are never persisted.

## Purchase flow

1. `initiate-purchase` authorizes an amount against a provisioned token and
   returns a `purchase_id`.
2. `payment-credentials` returns a one-time **cryptogram** (and a DPAN) used to
   settle the transaction on the network.

## Security principles

- **Never** collect card numbers in a chat conversation.
- Store only non-sensitive metadata (token id, last4, brand, expiry).
- Use short-lived secure tokens to authorize API calls.
- Confirm the total and payment method with the user before charging.
