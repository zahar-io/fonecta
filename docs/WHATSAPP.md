# WhatsApp channel (Meta WhatsApp Cloud API)

**What works now:** interactive messages with 3 reply buttons (Approve / Edit / No thanks), plain-text follow-ups, and a webhook (`/webhook/whatsapp`) that turns a button tap into a decision (approve, decline, edit in the chat, or undo). There are no owner web pages.

## Switch it on (demo)
1. Meta developer app with the WhatsApp product (free test number, or our own number). Add the demo phones as recipients.
2. Run the app with `WA_PHONE_NUMBER_ID`, `WA_TOKEN`, `WA_VERIFY_TOKEN`, `WA_TO=<demo phone>`, and expose port 8800 through a tunnel so Meta can reach `/webhook/whatsapp`.
3. Run `cloudflared tunnel --url http://localhost:8800` and set the webhook in Meta to `<tunnel>/webhook/whatsapp` with the verify token. Subscribe to `messages`.
4. **24 h rule:** a business can only send free-form or interactive messages within 24 h of the customer's last message. For the demo, the phone sends "hi" first.

## Production: an approved template (business-initiated)
Set `WA_TEMPLATE=connect_hours_suggestion` and `WA_TEMPLATE_LANG=fi|sv|nb|en`. Submit one template per language, category UTILITY:

```
Name: connect_hours_suggestion   Category: UTILITY   Language: fi
Body: {{1}}
Buttons (quick reply): Hyväksy | Muokkaa | Ei kiitos
Footer: Fonecta Connect
```
Our suggestion text goes into `{{1}}`. Each quick-reply button carries a signed payload, so the tap lands on the right suggestion, and only that one.
