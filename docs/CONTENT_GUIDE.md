# FOLDO content guide (UX writing)

How FOLDO talks to people. Use it for every label, message and page you add.
The UI language is **Thai**. English appears only where it is the name people
already use (see the glossary). The English column is the reference for a
future English version, not text to mix into the Thai UI.

## Voice

Professional, friendly, clear. Like a helpful senior who has done this before:
calm, specific, never salesy.

| Do | Don't |
|---|---|
| บันทึก “Backend Intern” แล้ว | บันทึกข้อมูลเรียบร้อยแล้วค่ะ! 🎉 |
| อีเมลไม่ถูกต้อง เช่น name@example.com | Invalid input |
| ยังไม่มีโปรเจกต์ เพิ่มโปรเจกต์แรกเพื่อให้พอร์ตโฟลิโอมีผลงานให้ดู | ปลดล็อกศักยภาพของคุณ เริ่มต้นการเดินทางเลย |
| ลบแล้วกู้คืนไม่ได้ | การดำเนินการนี้ไม่สามารถย้อนกลับได้ |

1. **One idea per sentence.** Cut words that don't change the meaning.
2. **Say what happens, then what to do.** "ยังไม่ได้บันทึก — แก้ 2 ช่องที่ไฮไลต์"
3. **Buttons are verbs + object.** "บันทึกโปรไฟล์", "เพิ่มทักษะ", "ลบโปรเจกต์" — never "ตกลง", "ยืนยัน", "ส่ง" alone.
   The confirm button repeats the action in the dialog title (title "ลบโปรเจกต์นี้?" → button "ลบโปรเจกต์").
4. **Errors are the system's job to explain**, not the user's fault: what's wrong + how to fix + an example when the format is the problem.
5. **No filler.** If a sentence would still be true on any other page, delete it.
6. **No exclamation marks** except a real celebration (almost never). No emoji in UI copy.
7. **Natural Thai, not translated English.** Write the Thai first. Avoid "ทำการ…", "ดำเนินการ…", "ได้ถูก…", "กรุณา…" chains.
   Use "คุณ" sparingly; Thai often reads better without a subject.
8. **No polite particles** (ค่ะ/ครับ/นะ) — the UI is not a person in a chat.

## Glossary

One concept, one word, everywhere (nav, titles, buttons, messages).

| Concept | Thai UI | English reference | Don't use |
|---|---|---|---|
| A set of personal info (`MainProfile`) | โปรไฟล์ | profile | Main profile (in Thai UI), ข้อมูลส่วนตัว |
| The default profile (`is_default`) | โปรไฟล์หลัก | main profile | Default, โปรไฟล์ Default |
| A portfolio version (`Portfolio`) | พอร์ตโฟลิโอ | portfolio | Portfolio (in Thai UI), เวอร์ชันพอร์ตโฟลิโอ |
| The idea of many tailored portfolios | หลายเวอร์ชัน (explanations only) | versions | — |
| Theme (`template_key`) | เทมเพลต | template | ธีม |
| Choose what a portfolio shows | เลือกเนื้อหา | choose content | ปรับเนื้อหา |
| Publish / unpublish | เผยแพร่ / เลิกเผยแพร่ | publish / unpublish | Publish, เปิดสาธารณะ |
| State: published / not | เผยแพร่แล้ว / ยังไม่เผยแพร่ | published / not published | ส่วนตัว, ฉบับร่าง, Private |
| Public page address | ลิงก์สาธารณะ | public link | URL, ลิงก์แชร์ |
| Share page (`share_kit`) | แชร์ลิงก์และ QR | share | Share Kit (as a page name) |
| Quality Check | ตรวจคุณภาพ | quality check | — |
| Severity | ต้องแก้ / ควรแก้ / คำแนะนำ | must fix / should fix / suggestion | Error / Warning / Info |
| Preview | ดูตัวอย่าง | preview | พรีวิว |
| Project (`Project`) | โปรเจกต์ | project | ผลงาน (for a project) |
| Project Story (feature name) | Project Story | Project Story | เรื่องเล่า |
| Story parts | ปัญหา · บทบาท · วิธีทำ · ทางออก · ผลลัพธ์ | problem · role · process · solution · outcome | Problem · ปัญหา |
| Education | การศึกษา | education | — |
| Skills / experience | ทักษะ / ประสบการณ์ | skills / experience | — |
| Skill levels | เริ่มต้น · ปานกลาง · ชำนาญ · เชี่ยวชาญ | beginner · intermediate · advanced · expert | Beginner… (in Thai UI) |
| Sign in / sign up / sign out | เข้าสู่ระบบ / สมัครสมาชิก / ออกจากระบบ | sign in / sign up / sign out | ล็อกอิน, Login |
| Brand tagline | One Profile. Many Forms. (kept in English) | — | translated tagline |

Keep in English: FOLDO, PDF, QR code, LinkedIn, GitHub, GPA, Desktop/Mobile
(preview sizes), Project Story.

**The portfolio itself** (themes, PDF) is the student's document for employers and
keeps its English section headings. This guide covers the app around it.

## Message patterns

| Situation | Pattern | Example |
|---|---|---|
| Saved | บันทึก “{name}” แล้ว | บันทึก “Kasetsart University” แล้ว |
| Added | เพิ่ม{thing} “{name}” แล้ว | เพิ่มทักษะ “Python” แล้ว |
| Deleted | ลบ “{name}” แล้ว | ลบ “FOLDO” แล้ว |
| Saved but incomplete | บันทึกแล้ว แต่{what} ยังขาด {fields} | บันทึก “Design” แล้ว แต่พอร์ตโฟลิโอยังต้องใช้ หัวข้อแนะนำตัว |
| Validation failed (toast) | ยังไม่ได้บันทึก — แก้ช่องที่ไฮไลต์ ข้อมูลอื่นยังอยู่ครบ | — |
| System failure | {action}ไม่สำเร็จเพราะระบบขัดข้องชั่วคราว {state} ลองอีกครั้ง | บันทึกไม่สำเร็จเพราะระบบขัดข้องชั่วคราว ข้อมูลที่กรอกยังอยู่ในฟอร์ม ลองอีกครั้ง |
| Required field | ต้องกรอก{label} (or ต้องกรอกช่องนี้) | ต้องกรอกชื่อโปรเจกต์ |
| Bad format | {thing}ไม่ถูกต้อง เช่น {example} | ลิงก์ไม่ถูกต้อง เช่น github.com/yourname |
| Empty state | ยังไม่มี{thing} + why it matters (one line) + one button | ยังไม่มีทักษะ ใส่ 5–8 ทักษะหลักพร้อมระดับความชำนาญ [เพิ่มทักษะ] |
| Destructive confirm | Title: ลบ{thing}นี้? · Body: what disappears + where else + "กู้คืนไม่ได้" · Button: ลบ{thing} | — |
| Loading | กำลัง{verb}… | กำลังบันทึก… |

## Before shipping a page

- Title, nav label and the button that opens the page use the same word.
- Every error says how to fix it; every empty state has one next action.
- After any action the user can see that it worked (toast, badge or state).
- No English sentence left in the Thai UI except glossary terms.
- Read it aloud. If it sounds like a translation, rewrite it.
