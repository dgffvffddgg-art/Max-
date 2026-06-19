# 🛡️ بوت حماية جروبات تليجرام

بوت تليجرام بيراقب رسائل الأعضاء تلقائيًا ويحذف أي رسالة فيها:
- ألفاظ غير لائقة / شتايم
- سبام إعلاني (روابط ترويجية، كلمات مشبوهة)
- فلود (رسائل كتير بسرعة)
- تكرار حروف مبالغ فيه (زي: ههههههههههه)
- عدد روابط مبالغ فيه في رسالة واحدة

ولما يحذف رسالة، بيبعت **تحذير محترم** للعضو (وبيتمسح تلقائي بعد شوية عشان متبوظش شكل الجروب). بعد **3 تحذيرات** بيتم **كتم العضو تلقائيًا** لمدة ساعة (قابلة للتعديل).

---

## 📋 الخطوة 1: إنشاء البوت والحصول على التوكن

1. افتح تليجرام وابحث عن [@BotFather](https://t.me/BotFather)
2. ابعتله الأمر `/newbot`
3. اختار اسم للبوت، وبعدين username لازم ينتهي بـ `bot` (مثال: `MyGroupGuardBot`)
4. هيديك **توكن** شكله كده: `123456789:ABCdefGhIJKlmnoPQRstuVwxyZ`
5. احتفظ بالتوكن ده، هتحتاجه بعد شوية

---

## 💻 الخطوة 2: التشغيل محليًا للتجربة

```bash
# 1. نزّل المشروع أو فك الضغط عنه
cd telegram-guard-bot

# 2. اعمل virtual environment (اختياري بس مفضّل)
python3 -m venv venv
source venv/bin/activate      # على Windows: venv\Scripts\activate

# 3. نزّل المكتبات المطلوبة
pip install -r requirements.txt

# 4. اعمل نسخة من ملف الإعدادات
cp .env.example .env

# 5. افتح ملف .env وحط التوكن بتاعك
# BOT_TOKEN=التوكن_اللي_خدته_من_BotFather

# 6. شغّل البوت
python bot.py
```

لو شفت في التيرمنال: `🛡️ البوت بدأ يشتغل...` يبقى البوت شغال صح.

---

## 👥 الخطوة 3: إضافة البوت للجروب

1. افتح الجروب اللي عايز تحميه
2. روح لإعدادات الجروب → **Administrators** → **Add Admin**
3. دور على البوت بالـ username بتاعه وضيفه
4. **مهم جدًا**: فعّل الصلاحيات دي للبوت:
   - ✅ Delete messages (حذف الرسائل)
   - ✅ Ban/Restrict users (حظر/تقييد الأعضاء) — عشان يقدر يكتم

من غير الصلاحيتين دول، البوت مش هيقدر يحذف أو يكتم.

---

## ⚙️ تخصيص الإعدادات

### الكلمات الممنوعة
افتح `config.py` وعدّل قائمة `BANNED_WORDS` و`SPAM_KEYWORDS` بالكلمات اللي عايز تمنعها. القائمة الحالية تجريبية فقط.

### تعديل عدد الإنذارات أو مدة الكتم
في ملف `.env`:
```
MUTE_DURATION_MINUTES=60       # مدة الكتم بالدقايق
WARNING_MESSAGE_LIFETIME=15    # كام ثانية تفضل رسالة التحذير قبل ما تتمسح
```
عدد الإنذارات قبل الكتم (افتراضي 3) موجود في `config.py` تحت اسم `MAX_WARNINGS`.

### حساسية كشف الفلود والسبام
كمان في `config.py`:
```python
MAX_MESSAGES_PER_WINDOW = 5      # أقصى عدد رسائل
TIME_WINDOW_SECONDS = 10          # خلال كام ثانية
MAX_LINKS_PER_MESSAGE = 3         # أقصى روابط في رسالة واحدة
MAX_REPEATED_CHARS = 6            # تكرار الحرف الواحد
```

---

## 🔧 أوامر الأدمن داخل الجروب

| الأمر | الوصف |
|---|---|
| `/start` | يتأكد إن البوت شغال |
| `/warnings` (كـ reply على رسالة عضو) | يعرض عدد إنذاراته الحالية |
| `/resetwarn` (كـ reply على رسالة عضو) | يصفّر إنذارات العضو ده (للأدمن بس) |

---

## ☁️ رفع المشروع على GitHub

```bash
git init
git add .
git commit -m "إنشاء بوت حماية جروبات تليجرام"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```

⚠️ **تنبيه أمان مهم**: ملف `.env` مُستبعد تلقائيًا من الرفع (موجود في `.gitignore`) عشان التوكن بتاعك متترفعش لأي حد. لو حد لقى توكن البوت بتاعك، يقدر يتحكم في البوت بالكامل — لو حصل كده اعمل `/revoke` من BotFather واخد توكن جديد فورًا.

---

## 🚀 الاستضافة: رفع الكود على GitHub ثم تشغيله على Railway أو Render

⚠️ **ملحوظة مهمة**: GitHub بيخزّن الكود بس، مش بيشغّله. علشان كده محتاجين نربطه بمنصة استضافة (Railway أو Render) بتسحب الكود من الـ repo وتشغّله 24 ساعة فعليًا. **GitHub Actions مش مناسب هنا** لأنه مصمم لمهام مؤقتة (حد أقصى 6 ساعات للمهمة) مش لبرنامج مراقبة شغال باستمرار زي البوت ده.

### الخطوة 1: ارفع الكود على GitHub
```bash
git init
git add .
git commit -m "إنشاء بوت حماية جروبات تليجرام"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git push -u origin main
```
ملف `.env` (اللي فيه التوكن الحقيقي) مُستبعد تلقائيًا من الرفع بسبب `.gitignore` — متحطش التوكن في أي مكان هيتنشر على GitHub.

### الخطوة 2أ: التشغيل على Railway (الأسهل)
1. روح [railway.app](https://railway.app) وسجّل دخول بحساب GitHub
2. اضغط **New Project** → **Deploy from GitHub repo**
3. اختار الـ repo بتاع البوت
4. روح لتبويب **Variables** وضيف:
   - `BOT_TOKEN` = التوكن بتاعك من BotFather
   - `MUTE_DURATION_MINUTES` = `60`
   - `WARNING_MESSAGE_LIFETIME` = `15`
5. Railway هيكتشف ملف `Procfile` تلقائيًا ويشغّل `python bot.py` كـ worker
6. خلاص، البوت هيشتغل ويفضل شغال 24 ساعة

### الخطوة 2ب: أو التشغيل على Render
1. روح [render.com](https://render.com) وسجّل دخول بحساب GitHub
2. اضغط **New** → **Background Worker**
3. اربطه بالـ repo بتاعك
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python bot.py`
6. تحت **Environment Variables** ضيف نفس المتغيرات اللي فوق (`BOT_TOKEN` وغيره)
7. اضغط **Create Background Worker**

> اخترت **Background Worker** مش **Web Service** لأن البوت مفيهوش سيرفر HTTP بيستقبل طلبات، هو بس عملية شغالة بتعمل polling لتليجرام.

### ملاحظة عن الباقة المجانية
كل من Railway وRender بيوفروا باقة مجانية بحدود استخدام شهرية (ساعات تشغيل أو رصيد دولاري). البوت ده خفيف جدًا على الموارد فهيغطّيه الرصيد المجاني غالبًا، لكن تابع استهلاكك من لوحة التحكم بتاعت المنصة.

قولّي لو واجهتك أي مشكلة في أي خطوة من الخطوات دي.

---

## 📁 هيكل المشروع

```
telegram-guard-bot/
├── bot.py              # الكود الرئيسي وربط كل حاجة
├── config.py           # الإعدادات والكلمات الممنوعة
├── filters.py          # منطق كشف الشتايم والسبام والفلود
├── database.py         # تخزين عدد إنذارات كل عضو (SQLite)
├── requirements.txt    # المكتبات المطلوبة
├── Procfile             # يخبر Railway/Render بأمر التشغيل
├── runtime.txt          # نسخة Python المستخدمة
├── .env.example         # نموذج لملف البيئة (انسخه لـ .env)
└── .gitignore
```
