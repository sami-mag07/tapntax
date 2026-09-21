# The iPhone side, without an app

Apple gives no third party access to Apple Pay transactions. FinanceKit reads only
Apple Card, Apple Cash and Savings, needs an entitlement Apple reviews per app, and
Apple Card does not exist in Germany. What does work, on any iPhone, in two minutes,
is a Shortcuts automation. It fires on every Wallet payment and hands you the card,
the merchant and the amount.

## Build it

1. Shortcuts, **Automation** tab, **+**, trigger **Wallet** (called **Transaction**
   on iOS 17 and 18). Pick the cards it should watch. Choose **Run Immediately** so
   nothing has to be confirmed.
2. Add **Get Contents of URL**
   - URL: `https://your-server/v1/payment`
   - Method: **POST**, Request Body: **JSON**
   - `merchant` = Shortcut Input, property **Merchant**
   - `amount` = Shortcut Input, property **Amount**
   - `card` = Shortcut Input, property **Card**
3. Add **Get Dictionary Value**, key `shortcut.notification`, from the result above.
4. Add **Show Notification** with that value as the body.

That is the whole loop: pay, and the question is on the lock screen before the
receipt printer stops.

## Answering from the phone

The simplest version adds **Choose from Menu** after the notification with
*Business* and *Private*, and a second **Get Contents of URL** posting
`{"id": <entry id>, "answer": "business"}` to `/v1/answer`. The entry id comes back
in the same response as `entry.id`.

For a product you would put those two buttons on the notification itself, which
needs a real app, and then the Shortcut is only the pilot.

## Known limits

- The trigger occasionally times out when the card issuer's own notification is slow.
  The payment is not lost, it just arrives late.
- The merchant string is whatever the terminal wrote: `REWE SAGT DANKE 4821`,
  `SUMUP *K42`. `rules.brand()` normalises what it can, and the classifier asks when
  it cannot.
- There is no merchant category code in the Wallet trigger. Bank data over PSD2
  carries it, which is one reason the production path is the bank.
