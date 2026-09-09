Oracle of Runes - GitHub APK Builder
===================================

هذه النسخة لا تحتاج فتح مشروع ScummVM داخل Android Studio، ولا تحتاج WSL على جهازك.
GitHub Actions يبني APK على سيرفر Ubuntu ثم يعطيك الملف جاهز للتنزيل.

مهم:
- اللعبة الأصلية موجودة في game_data/runes7.dxr مع Runes.dat و Runes.skr.
- يتم تعديل ScummVM Director حتى يتعرف على Oracle of Runes باسم target: orunes.
- البناء الحالي arm64-v8a، مناسب لمعظم أجهزة Android الحديثة.
- الهدف الأول هو تشغيل ملفات اللعبة الأصلية كما هي، وليس إعادة برمجة اللعبة.

الطريقة:
1) أنشئ Repository جديد وفاضي على GitHub، مثلا Oracle-of-Runes-Android.
2) ارفع كل محتويات هذا المجلد إلى الـRepository، بما فيها المجلد المخفي .github.
3) افتح تبويب Actions في GitHub.
4) اختر: Build Oracle of Runes Android APK
5) اضغط Run workflow ثم Run workflow.
6) انتظر حتى تصبح العلامة خضراء.
7) افتح الـRun ثم انزل إلى Artifacts.
8) نزّل Oracle-of-Runes-Android.
9) فك الضغط وستجد Oracle-of-Runes-debug.apk وملفات اللعبة الأصلية.

إذا فشل الـAction:
افتح الخطوة الحمراء، انسخ آخر 30-50 سطر أو خذ Screenshot وأرسلها إلى ChatGPT.

ملاحظة تقنية:
الـAPK مبني من ScummVM مع Director فقط وتعريف خاص ببصمة runes7.dxr الموجودة في نسختك.
ملفات اللعبة تُحفظ كذلك داخل أصول APK، لكن التشغيل المباشر بدون واجهة ScummVM يعتمد على كيفية تعامل إصدار Android الحالي من ScummVM مع game assets. إذا فتح Launcher بدل اللعبة، هذه ليست إعادة بناء للعبة؛ نعدل مرحلة الإقلاع التالية فقط مع بقاء runes7.dxr الأصلي.
