import streamlit as st
import pandas as pd
import re
import io

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="مدقق الرواتب - مصرف الرافدين",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS لتحسين العرض ---
st.markdown("""
<style>
    .main { direction: rtl; text-align: right; }
    .stAlert { direction: rtl; text-align: right; }
    div[data-testid="stMarkdownContainer"] p { font-size: 16px; }
    .stDataFrame { direction: ltr; } 
</style>
""", unsafe_allow_html=True)

# --- دوال المنطق ---
def find_columns(df):
    iban_col = None
    amount_col = None
    payer_col = None

    for col in df.columns:
        c_low = str(col).lower().strip()
        
        # البحث عن حساب المستفيد
        if (("beneficiary" in c_low) and ("account" in c_low or "acount" in c_low or "iban" in c_low)) and "payer" not in c_low:
            iban_col = col
        # البحث عن حساب الدافع
        if "payer" in c_low and ("account" in c_low or "acount" in c_low):
            payer_col = col
        # البحث عن المبلغ
        if "amount" in c_low or "مبلغ" in c_low or "راتب" in c_low:
            amount_col = col
            
    return iban_col, amount_col, payer_col

def clean_amount_val(val):
    """
    دالة تنظيف ذكية للمبالغ:
    - تتعامل مع 1,000,000
    - تتعامل مع 1.000.000 (تنسيق عراقي شائع بالخطأ)
    """
    val_str = str(val)
    
    # 1. حذف المسافات
    val_str = val_str.replace(" ", "")
    
    # 2. حذف الفواصل (,)
    val_str = val_str.replace(",", "")
    
    # 3. معالجة النقاط (.)
    # إذا كان هناك أكثر من نقطة (مثلاً 1.250.000)، نحذفها كلها ونعتبرها فواصل آلاف
    if val_str.count(".") > 1:
        val_str = val_str.replace(".", "")
    
    # 4. إبقاء الأرقام والنقطة العشرية الوحيدة (إن وجدت)
    clean = re.sub(r'[^\d.]', '', val_str)
    
    try:
        return float(clean)
    except:
        return 0.0

def check_iban_mod97(iban):
    try:
        if not iban.startswith("IQ") or len(iban) != 23:
            return False
        rearranged = iban[4:] + iban[:4]
        numeric_iban = ""
        for char in rearranged:
            if char.isdigit(): numeric_iban += char
            else: numeric_iban += str(ord(char) - 55)
        return int(numeric_iban) % 97 == 1
    except: return False

# --- واجهة التطبيق ---
st.title("🏦 نظام تدقيق الرواتب (Streamlit)")
st.markdown("---")

uploaded_file = st.file_uploader("📂 اختر ملف الرواتب (Excel)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # قراءة الملف كنص لضمان دقة الايبان، ثم نعالج المبالغ يدوياً
        df = pd.read_excel(uploaded_file, dtype=str)
        df.columns = df.columns.str.strip()
        
        iban_col, amount_col, payer_col = find_columns(df)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if iban_col: st.success(f"✅ المستفيد: {iban_col}")
            else: st.error("❌ لم نجد عمود المستفيد")
        with c2:
            if payer_col: st.success(f"✅ الدافع: {payer_col}")
            else: st.warning("⚠️ لا يوجد عمود Payer (اختياري)")
        with c3:
            if amount_col: st.success(f"✅ المبلغ: {amount_col}")
            else: st.error("❌ لم نجد عمود المبلغ")

        if not iban_col or not amount_col:
            st.stop()

        tab1, tab2 = st.tabs(["🔍 تقرير الفحص", "🛠️ تنظيف وتحميل"])

        # === التبويب 1: الفحص ===
        with tab1:
            if st.button("بدء الفحص", key="btn_audit"):
                
                critical_errors = []
                warnings_list = []
                seen_ibans = {}
                
                progress_bar = st.progress(0)
                
                for index, row in df.iterrows():
                    row_num = index + 2
                    progress_bar.progress((index + 1) / len(df))
                    
                    # --- 1. فحص المستفيد ---
                    raw_iban = str(row[iban_col])
                    if raw_iban.lower() == 'nan': raw_iban = ""

                    # >> كشف الأحرف الصغيرة (Regex) <<
                    if re.search(r'[a-z]', raw_iban):
                         critical_errors.append(f"❌ [صف {row_num}] تنسيق خطأ: الايبان يحتوي على أحرف صغيرة (Small): {raw_iban}")

                    if " " in raw_iban:
                        warnings_list.append(f"⚠️ [صف {row_num}] مسافة زائدة في حساب المستفيد.")
                    
                    clean_iban = raw_iban.replace(" ", "").strip().upper()
                    
                    if not check_iban_mod97(clean_iban):
                        critical_errors.append(f"❌ [صف {row_num}] حساب المستفيد خطأ (رياضياً أو الطول): {clean_iban}")
                    
                    if clean_iban in seen_ibans:
                        warnings_list.append(f"📝 [صف {row_num}] تنبيه تكرار: مكرر مع الصف {seen_ibans[clean_iban]}.")
                    else:
                        seen_ibans[clean_iban] = row_num

                    # --- 2. فحص الدافع ---
                    if payer_col:
                        raw_payer = str(row[payer_col])
                        if raw_payer.lower() == 'nan': raw_payer = ""
                        
                        if re.search(r'[a-z]', raw_payer):
                            critical_errors.append(f"❌ [صف {row_num}] حساب الدافع يحتوي على أحرف صغيرة: {raw_payer}")

                        clean_payer = raw_payer.replace(" ", "").strip().upper()
                        if raw_payer and not check_iban_mod97(clean_payer):
                            critical_errors.append(f"❌ [صف {row_num}] حساب الدافع خطأ: {clean_payer}")
                            
                    # --- 3. فحص المبلغ (تم تحسينه) ---
                    amt = clean_amount_val(row[amount_col])
                    
                    # نعتبر المبلغ خطأ فقط إذا كان صفر، ولكن نتجاهل الصفوف الفارغة تماماً
                    is_empty_row = (raw_iban == "" and str(row[amount_col]).lower() == 'nan')
                    
                    if not is_empty_row and amt <= 0:
                        critical_errors.append(f"❌ [صف {row_num}] المبلغ صفر أو غير صالح (القيمة: {row[amount_col]})")

                # --- النتائج ---
                if len(critical_errors) > 0:
                    st.error(f"⛔ وجدنا {len(critical_errors)} أخطاء:")
                    for err in critical_errors:
                        st.write(err)
                    st.markdown("---")
                else:
                    st.success("✅ الملف سليم تماماً (لا توجد أخطاء رياضية أو تنسيق).")

                if len(warnings_list) > 0:
                    st.warning(f"⚠️ يوجد {len(warnings_list)} تنبيهات (يمكن تجاهلها):")
                    with st.expander("عرض التنبيهات"):
                        for warn in warnings_list:
                            st.write(warn)
                
                if len(critical_errors) == 0 and len(warnings_list) == 0:
                    st.balloons()

        # === التبويب 2: التنظيف ===
        with tab2:
            st.info("هنا يتم إصلاح الملف (تحويل للكبير، إصلاح المبالغ) تلقائياً.")
            
            df_clean = df.copy()
            
            # تنظيف المستفيد
            df_clean[iban_col] = df_clean[iban_col].astype(str).str.replace(" ", "").str.strip().str.upper()
            
            # تنظيف الدافع
            if payer_col:
                df_clean[payer_col] = df_clean[payer_col].astype(str).str.replace(" ", "").str.strip().str.upper()
                
            # تنظيف المبلغ باستخدام الدالة المحسنة
            df_clean[amount_col] = df_clean[amount_col].apply(lambda x: f"{clean_amount_val(x):.0f}")
            
            st.dataframe(df_clean.head())
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_clean.to_excel(writer, index=False)
                
            st.download_button(
                label="📥 تحميل الملف الجاهز (Excel)",
                data=buffer,
                file_name="Salary_Cleaned.xlsx",
                mime="application/vnd.ms-excel"
            )

    except Exception as e:
        st.error(f"حدث خطأ: {e}")
 
