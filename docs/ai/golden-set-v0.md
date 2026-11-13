# Golden Set v0 — Draft for Correction (task I0-02)

Fifty colloquial Persian customer messages with the expected extraction result, used to
measure order-extraction accuracy (QA-AI1) and grounding (QA-AI2) from Iteration 0 onwards.
This is a **draft written by the Lead agent**. The author corrects it, adds messages of their
own, and only then it becomes the labeled set. After correction it is converted to
`docs/ai/golden-set-v0.jsonl` (one JSON object per row, schema below) for the evaluation script.

How to read the table:

- **Intent** is one of the SAD 9.2 intents: `add_items`, `remove_item`, `change_quantity`,
  `ask_info`, `order_status`, `cancel_order`, `out_of_scope`.
- **Expected items** use the sample menu IDs below as `product_id × qty`. `—` means no items.
- **Expected behaviour** states what the system must do: place the order, ask a clarifying
  question (SAD 9.3 rules: unresolved mention, confidence below 0.7, quantity outside 1–20),
  answer from retrieved facts, or say it does not know.
- Messages deliberately contain typos, Persian and Arabic letter variants (ي/ی, ك/ک), missing
  half-spaces, Persian digits, number words, and colloquial forms (C-06).

## Sample menu used for labels

| product_id | Name (Persian) | Category | Price (IRT) | Aliases |
| --- | --- | --- | --- | --- |
| p_01 | همبرگر مرغ | burger | 185000 | همبر مرغ، برگر مرغ |
| p_02 | همبرگر گوشت | burger | 220000 | همبر گوشت، برگر گوشت |
| p_03 | چیزبرگر | burger | 240000 | چیز برگر |
| p_04 | پیتزا مخصوص | pizza | 350000 | مخصوص |
| p_05 | پیتزا پپرونی | pizza | 330000 | پپرونی |
| p_06 | پیتزا سبزیجات | pizza | 290000 | سبزیجات، وجی |
| p_07 | مرغ سوخاری | fried | 260000 | سوخاری |
| p_08 | سیب‌زمینی سرخ‌کرده | side | 80000 | سیب زمینی، سیبزمینی، فرنچ فرایز |
| p_09 | نوشابه خانواده | drink | 40000 | نوشابه بزرگ |
| p_10 | نوشابه قوطی | drink | 25000 | نوشابه کوچیک، قوطی |
| p_11 | دوغ | drink | 20000 | — |
| p_12 | سالاد سزار | salad | 150000 | سزار |
| p_13 | سالاد فصل | salad | 70000 | — |
| p_14 | ساندویچ هات‌داگ | sandwich | 120000 | هات داگ |
| p_15 | ساندویچ فلافل | sandwich | 90000 | فلافل |
| p_16 | چلوکباب کوبیده | iranian | 280000 | کوبیده، چلو کباب |
| p_17 | جوجه کباب | iranian | 300000 | جوجه |
| p_18 | زرشک‌پلو با مرغ | iranian | 250000 | زرشک پلو |
| p_19 | آب معدنی | drink | 15000 | آب |
| p_20 | سس اضافه | side | 10000 | سس |

Rows marked "order context" assume an existing order in the session; the evaluation script
seeds the session with the order listed in the notes.

## Messages

| # | Message (Persian) | Intent | Expected items | Expected behaviour / notes |
| --- | --- | --- | --- | --- |
| 1 | دو تا همبر مرغ با یه نوشابه خانواده | add_items | p_01×2, p_09×1 | Place order. Baseline example from SAD 11.4. |
| 2 | ۳ تا پیتزا پپرونی بزرگ میخوام | add_items | p_05×3 | Place order. Persian digit; "بزرگ" (size) has no menu meaning and is ignored. |
| 3 | یه چیزبرگر و دوتا سیب زمینی لطفا | add_items | p_03×1, p_08×2 | Place order. Alias without half-space. |
| 4 | سلام، میشه ۱ عدد جوجه کباب برام بفرستین؟ | add_items | p_17×1 | Place order. Greeting plus polite request. |
| 5 | یه پیتزا میخوام | add_items | — | Clarify: which pizza (three candidates). `unresolved_mentions: ["پیتزا"]`. |
| 6 | همبرگر | add_items | — | Clarify: chicken, beef or cheese. Single-word message. |
| 7 | نوشابه رو حذف کن | remove_item | p_09 | Order context: #1. Resolve "نوشابه" to the soda already in the order. |
| 8 | همبرگرا رو کن سه تا | change_quantity | p_01×3 | Order context: #1. Colloquial plural "همبرگرا". |
| 9 | سوخاری تنده؟ | ask_info | p_07 | Answer from item description; if spiciness is not in the facts, say it does not know. |
| 10 | پیتزا مخصوص چنده؟ | ask_info | p_04 | Answer the display price 350000 from the projection. |
| 11 | سفارشم کجاست؟ | order_status | — | Read status from Order. Order context: #1 in status CREATED. |
| 12 | کنسلش کن | cancel_order | — | Order context: #1 in CREATED → cancel. In ACCEPTED → explain only staff can cancel. |
| 13 | هوا امروز چطوره؟ | out_of_scope | — | Polite reply, redirect to the menu. |
| 14 | دوتا کوبیده با دوغ | add_items | p_16×2, p_11×1 | Place order. "با دوغ" with no number means one. |
| 15 | یه زرشک پلو با مرغ و یه آب معدنی | add_items | p_18×1, p_19×1 | Place order. "با مرغ" is part of the item name, not a second item. |
| 16 | ۲تا هات داگ و ۲ تا نوشابه قوطی | add_items | p_14×2, p_10×2 | Place order. Digit glued to "تا". |
| 17 | چهار تا فلافل میخوام | add_items | p_15×4 | Place order. Number word. |
| 18 | یه سالاد سزار هم اضافه کن | add_items | p_12×1 | Order context: #1. Append to existing order (`PATCH items`). |
| 19 | سس اضافه هم بذار | add_items | p_20×1 | Order context: #1. "اضافه" is part of the item name. |
| 20 | پیتزا سبزیجات پنیر داره؟ | ask_info | p_06 | Answer from ingredients in the description. |
| 21 | چیزبرگر چقدره؟ | ask_info | p_03 | Answer display price 240000. |
| 22 | همبرگر گوشتتون حلاله؟ | ask_info | p_02 | Not in facts → say it does not know, offer to ask staff. Never invent. |
| 23 | سیبزمینی رو حذف کن | remove_item | p_08 | Order context: #3. Typo without space. |
| 24 | نوشابه خانواده رو بکن ۲ تا | change_quantity | p_09×2 | Order context: #1. |
| 25 | دو تا از همون پیتزا پپرونی | add_items | p_05×2 | Place order. Colloquial "همون". |
| 26 | یه همبرگر مرغ بدون پیاز | add_items | p_01×1 | Place order; the "no onion" request is not modeled in v1 → reply that customizations go in the order note or are not supported. Author decides. |
| 27 | میخوام سفارشمو عوض کنم، به جای کوبیده جوجه بزار | remove_item + add_items | −p_16, +p_17×1 | Order context: #14. Two operations in one message; expected as one `PATCH items` with removed and added lists. |
| 28 | سفارشم کی میرسه؟ | order_status | — | Status plus a generic preparation-time reply; no invented ETA. |
| 29 | بیخیال، نمیخوام | cancel_order | — | Order context: #1 in CREATED → cancel after confirmation button. |
| 30 | ممنون، خداحافظ | out_of_scope | — | Polite closing, no action. |
| 31 | ۱۰ تا نوشابه قوطی برای مهمونی | add_items | p_10×10 | Place order. Quantity within 1–20. |
| 32 | سی تا همبرگر گوشت | add_items | — | Quantity 30 is outside 1–20 → clarify / ask to contact the restaurant. |
| 33 | پیتزا پپرونی ۲ تا، سیب‌زمینی ۱ دونه، دوغ ۳ تا | add_items | p_05×2, p_08×1, p_11×3 | Place order. Quantity after the item name, "دونه" as counter. |
| 34 | یه دونه از اون سالاده که با کاهو و سس مخصوصه | add_items | — | Clarify between p_12 and p_13 unless the description makes Caesar unambiguous. |
| 35 | هم برگر مرغ ميخوام دو تا | add_items | p_01×2 | Place order. Arabic yeh (ي) and split word "هم برگر". |
| 36 | چلو کباب دارید؟ | ask_info | p_16 | Answer availability from the projection (`is_available`). |
| 37 | منو رو بفرست | ask_info | — | Send category list / quick replies, not the whole menu text. |
| 38 | یه پیتزا مخصوص خانواده | add_items | p_04×1 | Place order. "خانواده" is a size word here, must not match p_09 (نوشابه خانواده). |
| 39 | سفارش قبلیمو دوباره بزن | out_of_scope | — | Reorder is not in v1 scope → polite reply, offer the menu. |
| 40 | پیتزا پپرونی رو حذف کن و به جاش سبزیجات بزار | remove_item + add_items | −p_05, +p_06×1 | Order context: #33. Replacement in one message. |
| 41 | همبرگر مرغ ۱ عدد، نوشابه ۱ عدد | add_items | p_01×1 | Partial: clarify "نوشابه" (family vs can) before placing; author may prefer placing p_01 first. |
| 42 | من ۲ تا جوجه کباب سفارش داده بودم، یکیش رو کم کن | change_quantity | p_17×1 | Order context: p_17×2. Relative quantity change ("one less"). |
| 43 | یه فلافل با سیب زمینی و ی نوشابه قوطی | add_items | p_15×1, p_08×1, p_10×1 | Place order. "ی" as typo for "یه". |
| 44 | سوخاری چند تیکه است؟ | ask_info | p_07 | Answer from description if the piece count is there; otherwise say it does not know. |
| 45 | اینجا پارکینگ داره؟ | out_of_scope | — | Not menu-related → say it does not know, redirect. |
| 46 | دوتا مرغ سوخاری و یه سزار | add_items | p_07×2, p_12×1 | Place order. Alias "سزار". |
| 47 | پیتزا ۲ تا مخصوص | add_items | p_04×2 | Place order. Unusual word order. |
| 48 | چیز برگر رو کن ۴ تا | change_quantity | p_03×4 | Order context: #3. Alias with space. |
| 49 | وضعیت سفارش ۵۰۱ | order_status | — | Status by order reference; only if the order belongs to this customer and tenant. |
| 50 | شما تا ساعت چند بازید؟ | out_of_scope | — | Opening hours are not in v1 facts → say it does not know. Author may move this to `ask_info` if restaurant info is added to the knowledge base. |

## JSONL record shape (after correction)

```json
{"id": 1, "text": "دو تا همبر مرغ با یه نوشابه خانواده", "context_order": null,
 "expected": {"intent": "add_items",
              "items": [{"product_id": "p_01", "qty": 2}, {"product_id": "p_09", "qty": 1}],
              "removed_items": [], "clarify": false, "notes": ""}}
```

Scoring (SAD 17.3): a row is correct only when intent, every product ID and every quantity
match exactly; any product ID outside the menu counts as a made-up item (QA-AI2, must be zero).
