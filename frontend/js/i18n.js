/**
 * Multilingual UI Translation Service for LoanIQ.
 * Seamlessly integrates with Sarvam Mayura v1, persistent SQLite caching,
 * and built-in instant typography dictionaries for Marathi and Hindi.
 */

import { api } from "./api.js";

const CURRENT_LANG_KEY = "loaniq_ui_lang";
let currentLanguage = localStorage.getItem(CURRENT_LANG_KEY) || "en";
const baseStringMap = {};

export const UI_DICTIONARY = {
  mr: {
    // Header & Navigation
    system_status: "⚙️ स्थिती",
    sign_out: "बाहेर पडा",
    nav_dashboard: "डॅशबोर्ड",
    nav_recommendations: "कर्ज ऑफर",
    nav_compare: "कर्ज तुलना",
    nav_forecast: "रोख प्रवाह अंदाज",
    nav_optimizer: "कर्ज ऑप्टिमायझर",
    nav_profile: "प्रोफाइल आणि इतिहास",
    nav_assistant: "एआय कॉपायलट",
    notice_disclaimer: "",

    // Dashboard
    dash_welcome: "व्यापारी आर्थिक सारांश",
    dash_subtitle: "रिअल-टाइम खेळते भांडवल, सक्रिय कर्ज आणि क्रेडिट विश्लेषण.",
    dash_sales_label: "मासिक संदर्भ विक्री",
    dash_profit_label: "मासिक नफा संदर्भ",
    dash_score_label: "क्रेडिट स्कोअर",
    dash_daily_emi_label: "सध्याचा दैनिक ईएमआय",
    good_rating: "उत्तम रेटिंग",
    active_loans_suffix: "सक्रिय कर्जे",
    dash_loan_discovery_title: "कर्ज पात्रता आणि शोध",
    custom_criteria: "निकषांवर आधारित",
    dash_loan_discovery_desc: "तुमच्या व्यवसायाच्या गरजेनुसार, परतफेडीच्या क्षमतेनुसार आणि मंजूर होण्याच्या शक्यतेनुसार खेळत्या भांडवलाची कर्जे शोधा.",
    how_it_works_title: "📋 कर्ज शिफारसी कशा कार्य करतात:",
    how_it_works_steps: "१. आवश्यक कर्ज रक्कम (₹) टाका\n२. परतफेडीचा कालावधी (दिवस) निवडा\n३. परवडणारा कमाल दैनिक ईएमआय ठरवा\n४. तुमच्या निकषांनुसार पात्र कर्जे पहा",
    find_eligible_loans_btn: "🔍 पात्र कर्जे शोधा (रक्कम, कालावधी आणि ईएमआय भरा) →",
    dash_fc_preview_title: "३० दिवसांचा रोख प्रवाह अंदाज",
    view_analytics: "संपूर्ण विश्लेषण →",
    dash_fc_inflow_label: "अंदाजित विक्री आवक",
    dash_fc_expense_label: "अंदाजित खर्च",
    dash_fc_net_label: "निव्वळ कार्यप्रवाह",
    dash_fc_avg_daily_label: "सरासरी दैनिक शिल्लक",
    healthy_cashflow: "निरोगी रोख प्रवाह",
    direct_ml_forecast: "मशीन लर्निंग आधारित अंदाज",
    dash_active_debt_title: "सक्रिय कर्ज आणि परतफेड सारांश",
    optimize_loans_action: "कर्ज ऑप्टिमाइझ करा →",
    dash_debt_principal_label: "एकूण उर्वरित मुद्दल",
    dash_debt_repaid_label: "आतापर्यंत परत केलेले मुद्दल",

    // Recommendations Page
    recs_title: "वैयक्तिकृत कर्ज शिफारसी",
    recs_subtitle: "मागील स्वीकृती संभाव्यता, व्याजदर आणि रोख प्रवाह परवडण्याच्या आधारे क्रमवारी.",
    compare_selected_btn: "निवडलेली कर्जे तुलना करा",
    recs_step1_title: "पायरी १: तुमचे कर्ज निकष निश्चित करा",
    recs_step1_desc: "केवळ तिन्ही निकष पूर्ण करणारी उत्पादने शिफारस केली जातील",
    filter_amount: "आवश्यक रक्कम (₹)",
    filter_tenure: "कालावधी (दिवस)",
    filter_emi: "कमाल दैनिक ईएमआय (पर्यायी)",
    apply_filters_btn: "⚡ निकष लागू करा आणि पात्र कर्जे पहा",
    show_ineligible: "अपात्र उत्पादने दाखवा",
    eligible_badge: "पात्र",
    ineligible_badge: "अपात्र",
    acceptance_prob_label: "मंजुरी संभाव्यता:",
    daily_emi_label: "दैनिक ईएमआय",
    interest_rate_label: "व्याजदर",
    total_interest_label: "एकूण व्याज",
    processing_fee_label: "प्रक्रिया शुल्क",
    prepayment_fee_label: "प्रीपेमेंट शुल्क",
    affordability_label: "परवडण्याची क्षमता",
    click_for_modal: "🔍 सविस्तर विश्लेषण आणि ३-स्लायडर",
    why_product_title: "हे उत्पादन का योग्य:",

    // Comparison Page
    compare_title: "कर्ज उत्पादन तुलना",
    compare_subtitle: "व्याजदर, दैनिक ईएमआय, प्रक्रिया शुल्क आणि मंजुरीची शक्यता यांचे तुलनात्मक विश्लेषण.",
    back_to_offers: "← परत ऑफर्सकडे",
    best_overall_fit: "सर्वोत्तम पर्याय",
    lowest_interest_apr: "सर्वात कमी व्याजदर",
    fastest_repayment: "जलद परतफेड",
    highest_acceptance_prob: "सर्वाधिक स्वीकृती शक्यता",

    // Forecast Page
    fc_title: "रोख प्रवाह अंदाज विश्लेषण",
    fc_subtitle: "विक्री आवक, व्यावसायिक खर्च आणि निव्वळ दैनिक नफ्याचा मशीन लर्निंग अंदाज.",
    fc_refresh_btn: "🔄 अंदाज रीफ्रेश करा",
    fc_inflow_title: "अंदाजित विक्री आवक",
    fc_expense_title: "अंदाजित खर्च",
    fc_net_title: "निव्वळ कार्यप्रवाह",
    fc_avg_daily_title: "दैनिक सरासरी शिल्लक",
    fc_expected_receipts: "एकूण अपेक्षित आवक",
    fc_expected_outflow: "एकूण अपेक्षित खर्च",
    fc_inflow_minus_expenses: "आवक उणे खर्च",
    fc_daily_debt_capacity: "दैनिक कर्ज परतफेड क्षमता",
    fc_chart_title: "📈 दैनिक रोख प्रवाह मार्गक्रम",
    fc_chart_desc: "कालावधीनुसार विक्री आवक, व्यावसायिक खर्च आणि निव्वळ नफा यांची तुलना.",

    // Loan Optimizer Page
    opt_title: "कर्ज ऑप्टिमायझर आणि सिम्युलेटर",
    opt_subtitle: "सध्याच्या सक्रिय कर्जांची परतफेड सुलभ करा किंवा अंदाजित रोख प्रवाहावर नवीन कर्जाचे अनुकरण करा.",
    opt_tot_debt_lbl: "एकूण सक्रिय कर्ज",
    opt_daily_emi_lbl: "सध्याचा दैनिक ईएमआय",
    opt_avg_net_lbl: "सरासरी दैनिक निव्वळ प्रवाह",
    opt_free_cash_lbl: "ईएमआयनंतर शिल्लक रक्कम",
    opt_tab_old_btn: "🔄 सध्याची सक्रिय कर्जे ऑप्टिमाइझ करा (स्थिर व्याजदर)",
    opt_tab_new_btn: "➕ अतिरिक्त नवीन कर्जाचे सिम्युलेशन करा",
    opt_strat_title: "💡 कर्ज ऑप्टिमायझेशन आणि एकत्रीकरण धोरण",
    opt_active_sched_title: "सक्रिय कर्जांचे वेळापत्रक",
    opt_verified_accounts: "सत्यापित सावकार खाती",
    opt_select_loan_lbl: "ऑप्टिमाइझ करण्यासाठी सक्रिय कर्ज किंवा संपूर्ण पोर्टफोलिओ निवडा:",
    opt_capacity_meter_lbl: "दैनिक रोख प्रवाह क्षमता वि. एकूण कर्ज दायित्व",
    opt_existing_repay_title: "सक्रिय कर्ज परतफेड ऑप्टिमायझर",
    opt_existing_repay_desc: "करारातील व्याजदर बदलता येत नाही. उर्वरित मुद्दलावर दैनिक ईएमआय किंवा कालावधी बदलून परतफेडीचा वेग नियंत्रित करा.",
    opt_apr_fixed_badge: "🔒 करारानुसार व्याजदर निश्चित",
    opt_kpi_rem_debt: "उर्वरित कर्ज",
    opt_kpi_apr: "करार व्याजदर",
    opt_kpi_curr_emi: "सध्याचा ईएमआय",
    opt_kpi_tot_int: "उर्वरित व्याज",
    opt_slider_emi_lbl: "दैनिक ईएमआय हप्ता समायोजित करा",
    opt_slider_tenure_lbl: "उर्वरित कालावधी समायोजित करा (दिवस)",
    opt_new_sim_title: "नवीन कर्ज परस्परसंवादी सिम्युलेटर (स्लायडर)",
    opt_new_principal_lbl: "मंजूर मुद्दल रक्कम",
    opt_new_tenure_lbl: "कर्ज कालावधी (दिवस)",
    opt_new_emi_lbl: "दैनिक ईएमआय हप्ता",
    opt_new_apr_lbl: "वार्षिक व्याजदर (APR)",
    opt_run_sim_btn: "⚡ सिम्युलेशन चालवा",

    // Profile Page
    profile_title: "व्यापारी प्रोफाइल आणि कर्ज इतिहास",
    profile_subtitle: "सत्यापित व्यवसाय प्रोफाइल आणि ऐतिहासिक कर्ज खाती.",
    prof_biz_title: "व्यवसाय प्रोफाइल",
    prof_biz_name_lbl: "व्यवसायाचे नाव",
    prof_id_lbl: "व्यापारी आयडी",
    prof_type_lbl: "व्यवसायाचा प्रकार",
    prof_city_lbl: "शहर आणि श्रेणी",
    prof_age_lbl: "व्यवसाय वय",
    prof_sales_lbl: "मासिक संदर्भ विक्री",
    prof_profit_lbl: "मासिक नफा संदर्भ",
    prof_score_lbl: "क्रेडिट स्कोअर",
    prof_open_bal_lbl: "प्रारंभिक रोख शिल्लक",
    prof_pref_lang_lbl: "पसंतीची भाषा",
    prof_completed_title: "ऐतिहासिक पूर्ण झालेली कर्जे",

    // Popups: Loan Detail & 3-Slider Modal
    modal_loan_title: "कर्ज उत्पादन सविस्तर माहिती",
    modal_cost_composition: "वित्तपुरवठा खर्च रचना",
    modal_legend_principal: "■ मुद्दल:",
    modal_legend_interest: "■ एकूण व्याज:",
    modal_legend_fee: "■ शुल्क:",
    modal_kpi_principal_lbl: "मुद्दल",
    modal_kpi_emi_lbl: "दैनिक ईएमआय",
    modal_kpi_interest_lbl: "एकूण व्याज",
    modal_kpi_repay_lbl: "एकूण परतफेड",
    modal_opt_title: "परस्परसंवादी कर्ज अटी ऑप्टिमायझेशन",
    modal_opt_desc: "कर्ज रक्कम, कालावधी किंवा दैनिक ईएमआय स्लायडर समायोजित करा. आकडेमोड तत्काळ होते.",
    modal_amount_label: "मंजूर मुद्दल रक्कम",
    modal_tenure_label: "कर्ज कालावधी (दिवस)",
    modal_emi_label: "दैनिक कमी होणारा ईएमआय",
    modal_send_optimizer_btn: "⚡ कर्ज ऑप्टिमायझर कडे पाठवा →",
    modal_close_btn: "बंद करा",
    modal_amount_min_lbl: "किमान ₹10,000",
    modal_amount_limit_lbl: "उत्पादन मर्यादा",
    modal_amount_max_lbl: "कमाल ₹2,50,000",
    modal_safe_zone_msg: "✅ सुरक्षित झोन: दैनिक हप्ता तुमच्या अंदाजित रोख प्रवाहामध्ये व्यवस्थित बसतो.",
    modal_alert_zone_msg: "⚠️ सावधगिरी: दैनिक हप्ता अंदाजित रोख प्रवाह मर्यादेपेक्षा जास्त आहे!",

    // Status Modal
    status_modal_title: "सिस्टम स्थिती आणि मॉडेल तपशील",

    // AI Copilot
    chat_placeholder: "कर्जाविषयी विचारा किंवा रक्कम/ईएमआय सांगा...",
    send_btn: "पाठवा"
  },
  hi: {
    // Header & Navigation
    system_status: "⚙️ स्थिति",
    sign_out: "साइन आउट",
    nav_dashboard: "डैशबोर्ड",
    nav_recommendations: "ऋण ऑफ़र",
    nav_compare: "ऋण तुलना",
    nav_forecast: "कैश-फ्लो पूर्वानुमान",
    nav_optimizer: "ऋण ऑप्टिमाइज़र",
    nav_profile: "प्रोफ़ाइल और इतिहास",
    nav_assistant: "एआई कोपायलट",
    notice_disclaimer: "",

    // Dashboard
    dash_welcome: "व्यापारी वित्तीय सारांश",
    dash_subtitle: "रीयल-टाइम कार्यशील पूंजी, सक्रिय ऋण और क्रेडिट विश्लेषण।",
    dash_sales_label: "मासिक संदर्भ बिक्री",
    dash_profit_label: "मासिक लाभ संदर्भ",
    dash_score_label: "क्रेडिट स्कोर",
    dash_daily_emi_label: "वर्तमान दैनिक ईएमआई",
    good_rating: "उत्तम रेटिंग",
    active_loans_suffix: "सक्रिय ऋण",
    dash_loan_discovery_title: "ऋण पात्रता और खोज",
    custom_criteria: "मापदंड आधारित",
    dash_loan_discovery_desc: "अपनी व्यावसायिक आवश्यकताओं, पुनर्भुगतान क्षमता और स्वीकृति संभावना के अनुसार कार्यशील पूंजी ऋण खोजें।",
    how_it_works_title: "📋 ऋण अनुशंसा कैसे काम करती है:",
    how_it_works_steps: "1. आवश्यक ऋण राशि (₹) दर्ज करें\n2. पुनर्भुगतान अवधि (दिन) चुनें\n3. अधिकतम किफायती दैनिक ईएमआई तय करें\n4. अपनी शर्तों के अनुसार योग्य ऋण देखें",
    find_eligible_loans_btn: "🔍 योग्य ऋण खोजें (राशि, अवधि और ईएमआई दर्ज करें) →",
    dash_fc_preview_title: "30-दिवसीय कैश-फ्लो पूर्वानुमान",
    view_analytics: "पूरा विश्लेषण →",
    dash_fc_inflow_label: "अनुमानित बिक्री आवक",
    dash_fc_expense_label: "अनुमानित खर्च",
    dash_fc_net_label: "शुद्ध कार्यप्रवाह",
    dash_fc_avg_daily_label: "औसत दैनिक अधिशेष",
    healthy_cashflow: "स्वस्थ कैश-फ्लो",
    direct_ml_forecast: "मशीन लर्निंग पूर्वानुमान",
    dash_active_debt_title: "सक्रिय ऋण और पुनर्भुगतान सारांश",
    optimize_loans_action: "ऋण अनुकूलित करें →",
    dash_debt_principal_label: "कुल शेष मूलधन",
    dash_debt_repaid_label: "अब तक चुकाया गया मूलधन",

    // Recommendations Page
    recs_title: "व्यक्तिगत ऋण अनुशंसाएं",
    recs_subtitle: "स्वीकृति संभावना, ब्याज दरों और कैश-फ्लो वहन क्षमता के आधार पर रैंकिंग।",
    compare_selected_btn: "चयनित ऋणों की तुलना करें",
    recs_step1_title: "चरण 1: अपने ऋण मापदंड निर्धारित करें",
    recs_step1_desc: "केवल तीनों शर्तें पूरी करने वाले उत्पाद अनुशंसित होंगे",
    filter_amount: "अनुरोधित राशि (₹)",
    filter_tenure: "अवधि (दिन)",
    filter_emi: "अधिकतम दैनिक ईएमआई (वैकल्पिक)",
    apply_filters_btn: "⚡ शर्तें लागू करें और योग्य ऋण देखें",
    show_ineligible: "अपात्र उत्पाद दिखाएं",
    eligible_badge: "योग्य",
    ineligible_badge: "अयोग्य",
    acceptance_prob_label: "स्वीकृति संभावना:",
    daily_emi_label: "दैनिक ईएमआई",
    interest_rate_label: "ब्याज दर",
    total_interest_label: "कुल ब्याज",
    processing_fee_label: "प्रोसेसिंग शुल्क",
    prepayment_fee_label: "प्रीपेमेंट शुल्क",
    affordability_label: "वहन क्षमता",
    click_for_modal: "🔍 विस्तृत विश्लेषण और 3-स्लाइडर",
    why_product_title: "यह उत्पाद क्यों उपयुक्त है:",

    // Comparison Page
    compare_title: "ऋण उत्पाद तुलना",
    compare_subtitle: "ब्याज दरों, दैनिक ईएमआई, प्रोसेसिंग शुल्क और स्वीकृति संभावना का तुलनात्मक विश्लेषण।",
    back_to_offers: "← वापस ऑफ़र पर",
    best_overall_fit: "सर्वश्रेष्ठ विकल्प",
    lowest_interest_apr: "सबसे कम ब्याज दर",
    fastest_repayment: "त्वरित पुनर्भुगतान",
    highest_acceptance_prob: "उच्चतम स्वीकृति संभावना",

    // Forecast Page
    fc_title: "कैश-फ्लो पूर्वानुमान विश्लेषण",
    fc_subtitle: "बिक्री आवक, व्यावसायिक व्यय और शुद्ध दैनिक लाभ का मशीन लर्निंग अनुमान।",
    fc_refresh_btn: "🔄 पूर्वानुमान रीफ़्रेश करें",
    fc_inflow_title: "अनुमानित बिक्री आवक",
    fc_expense_title: "अनुमानित व्यय",
    fc_net_title: "शुद्ध परिचालन प्रवाह",
    fc_avg_daily_title: "दैनिक औसत अधिशेष",
    fc_expected_receipts: "कुल अपेक्षित आवक",
    fc_expected_outflow: "कुल अपेक्षित व्यय",
    fc_inflow_minus_expenses: "आवक घटाव व्यय",
    fc_daily_debt_capacity: "दैनिक ऋण वहन क्षमता",
    fc_chart_title: "📈 दैनिक कैश-फ्लो प्रक्षेपवक्र",
    fc_chart_desc: "समय के साथ बिक्री आवक, व्यावसायिक व्यय और शुद्ध लाभ की तुलना।",

    // Loan Optimizer Page
    opt_title: "ऋण अनुकूलक और सिम्युलेटर",
    opt_subtitle: "मौजूदा सक्रिय ऋणों का पुनर्भुगतान अनुकूलित करें या नए ऋण का अनुकरण करें।",
    opt_tot_debt_lbl: "कुल सक्रिय ऋण",
    opt_daily_emi_lbl: "वर्तमान दैनिक ईएमआई",
    opt_avg_net_lbl: "औसत दैनिक शुद्ध प्रवाह",
    opt_free_cash_lbl: "ईएमआई के बाद उपलब्ध नकदी",
    opt_tab_old_btn: "🔄 मौजूदा सक्रिय ऋण अनुकूलित करें (स्थिर ब्याज दर)",
    opt_tab_new_btn: "➕ अतिरिक्त नए ऋण का अनुकरण करें",
    opt_strat_title: "💡 ऋण अनुकूलन और समेकन रणनीति",
    opt_active_sched_title: "सक्रिय ऋण अनुसूची",
    opt_verified_accounts: "सत्यापित ऋणदाता खाते",
    opt_select_loan_lbl: "अनुकूलित करने के लिए सक्रिय ऋण या संपूर्ण पोर्टफोलियो चुनें:",
    opt_capacity_meter_lbl: "दैनिक कैश-फ्लो क्षमता बनाम कुल ऋण प्रतिबद्धता",
    opt_existing_repay_title: "सक्रिय ऋण पुनर्भुगतान अनुकूलक",
    opt_existing_repay_desc: "अनुबंध ब्याज दर नहीं बदली जा सकती। दैनिक ईएमआई या अवधि बदलकर पुनर्भुगतान की गति नियंत्रित करें।",
    opt_apr_fixed_badge: "🔒 अनुबंध ब्याज दर स्थिर",
    opt_kpi_rem_debt: "शेष ऋण",
    opt_kpi_apr: "अनुबंध ब्याज दर",
    opt_kpi_curr_emi: "वर्तमान ईएमआई",
    opt_kpi_tot_int: "शेष ब्याज",
    opt_slider_emi_lbl: "दैनिक ईएमआई किस्त समायोजित करें",
    opt_slider_tenure_lbl: "शेष अवधि समायोजित करें (दिन)",
    opt_new_sim_title: "नया ऋण इंटरएक्टिव सिम्युलेटर (स्लाइडर)",
    opt_new_principal_lbl: "स्वीकृत मूलधन राशि",
    opt_new_tenure_lbl: "ऋण अवधि (दिन)",
    opt_new_emi_lbl: "दैनिक ईएमआई किस्त",
    opt_new_apr_lbl: "वार्षिक ब्याज दर (APR)",
    opt_run_sim_btn: "⚡ सिमुलेशन चलाएं",

    // Profile Page
    profile_title: "व्यापारी प्रोफ़ाइल और ऋण इतिहास",
    profile_subtitle: "सत्यापित व्यावसायिक प्रोफ़ाइल और ऐतिहासिक ऋण खाते।",
    prof_biz_title: "व्यावसायिक प्रोफ़ाइल",
    prof_biz_name_lbl: "व्यवसाय का नाम",
    prof_id_lbl: "व्यापारी आईडी",
    prof_type_lbl: "व्यवसाय का प्रकार",
    prof_city_lbl: "शहर और श्रेणी",
    prof_age_lbl: "व्यवसाय की आयु",
    prof_sales_lbl: "मासिक संदर्भ बिक्री",
    prof_profit_lbl: "मासिक लाभ संदर्भ",
    prof_score_lbl: "क्रेडिट स्कोर",
    prof_open_bal_lbl: "प्रारंभिक नकद शेष",
    prof_pref_lang_lbl: "पसंदीदा भाषा",
    prof_completed_title: "ऐतिहासिक पूर्ण ऋण",

    // Popups: Loan Detail & 3-Slider Modal
    modal_loan_title: "ऋण उत्पाद विस्तृत विवरण",
    modal_cost_composition: "वित्तपोषण लागत संरचना",
    modal_legend_principal: "■ मूलधन:",
    modal_legend_interest: "■ कुल ब्याज:",
    modal_legend_fee: "■ शुल्क:",
    modal_kpi_principal_lbl: "मूलधन",
    modal_kpi_emi_lbl: "दैनिक ईएमआई",
    modal_kpi_interest_lbl: "कुल ब्याज",
    modal_kpi_repay_lbl: "कुल पुनर्भुगतान",
    modal_opt_title: "इंटरएक्टिव ऋण शर्तें अनुकूलन",
    modal_opt_desc: "ऋण राशि, अवधि या दैनिक ईएमआई स्लाइडर समायोजित करें। मान वास्तविक समय में पुनर्गणना करते हैं।",
    modal_amount_label: "स्वीकृत मूलधन राशि",
    modal_tenure_label: "ऋण अवधि (दिन)",
    modal_emi_label: "दैनिक घटती ईएमआई",
    modal_send_optimizer_btn: "⚡ ऋण अनुकूलक पर भेजें →",
    modal_close_btn: "बंद करें",
    modal_amount_min_lbl: "न्यूनतम ₹10,000",
    modal_amount_limit_lbl: "उत्पाद सीमा",
    modal_amount_max_lbl: "अधिकतम ₹2,50,000",
    modal_safe_zone_msg: "✅ सुरक्षित ज़ोन: दैनिक किस्त आपके पूर्वानुमानित कैश-फ्लो में आसानी से शामिल है।",
    modal_alert_zone_msg: "⚠️ चेतावनी: दैनिक किस्त पूर्वानुमानित कैश-फ्लो सीमा से अधिक है!",

    // Status Modal
    status_modal_title: "सिस्टम स्थिति और मॉडल मेटाडेटा",

    // AI Copilot
    chat_placeholder: "ऋण के बारे में पूछें या राशि/ईएमआई बताएं...",
    send_btn: "भेजें"
  }
};

export function getCurrentLanguage() {
  return currentLanguage;
}

export function t(key, fallback = "") {
  const lang = getCurrentLanguage();
  if (lang === "en") return fallback;
  const dict = UI_DICTIONARY[lang] || {};
  return dict[key] || fallback;
}

export function initI18n() {
  // Capture original English strings from all [data-i18n] elements
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!baseStringMap[key]) {
      baseStringMap[key] = el.textContent.trim();
    }
  });

  const selector = document.getElementById("lang-select");
  if (selector) {
    selector.value = currentLanguage;
    selector.addEventListener("change", async (e) => {
      await changeLanguage(e.target.value);
    });
  }

  if (currentLanguage !== "en") {
    changeLanguage(currentLanguage);
  }
}

export async function changeLanguage(targetLang) {
  currentLanguage = targetLang;
  localStorage.setItem(CURRENT_LANG_KEY, targetLang);

  const selector = document.getElementById("lang-select");
  if (selector && selector.value !== targetLang) {
    selector.value = targetLang;
  }

  if (targetLang === "en") {
    // Revert to English
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (baseStringMap[key]) {
        el.textContent = baseStringMap[key];
      }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key === "chat_placeholder") {
        el.setAttribute("placeholder", "Ask about loans or state amount/EMI...");
      }
    });
    window.dispatchEvent(new CustomEvent("languageChanged", { detail: { lang: "en" } }));
    return;
  }

  // 1. Immediately apply built-in dictionary so all pages and popups translate with zero latency
  const dict = UI_DICTIONARY[targetLang] || {};
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (dict[key]) {
      el.setAttribute("placeholder", dict[key]);
    }
  });

  // Notify active components to update dynamic text
  window.dispatchEvent(new CustomEvent("languageChanged", { detail: { lang: targetLang } }));

  // 2. Query persistent SQLite cache / Sarvam Mayura v1 API for any missing or custom strings
  const cacheKey = `loaniq_i18n_${targetLang}`;
  let cached = {};
  try {
    cached = JSON.parse(localStorage.getItem(cacheKey) || "{}");
  } catch (e) {
    cached = {};
  }

  const toTranslate = {};
  for (const [key, text] of Object.entries(baseStringMap)) {
    if (!cached[key] && !dict[key]) {
      toTranslate[key] = text;
    }
  }

  if (Object.keys(toTranslate).length > 0) {
    try {
      const res = await api.translation.translate({
        source_lang: "en",
        target_lang: targetLang,
        strings: toTranslate,
      });

      if (res && res.translations) {
        Object.assign(cached, res.translations);
        localStorage.setItem(cacheKey, JSON.stringify(cached));

        // Apply newly translated strings
        document.querySelectorAll("[data-i18n]").forEach((el) => {
          const key = el.getAttribute("data-i18n");
          if (cached[key]) {
            el.textContent = cached[key];
          }
        });
      }
    } catch (err) {
      console.warn("Sarvam translation call warning:", err);
    }
  }
}
