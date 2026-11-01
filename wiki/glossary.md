# Sudan News & OSINT Glossary: Cross-Lingual Entity & Place Disambiguation Registry (`wiki/glossary.md`)

> [!IMPORTANT] Canonical Disambiguation & Cross-Lingual Normalization Rules
> Incoming evidence in `raw/` spans Arabic (Modern Standard Arabic and Sudanese vernacular), English, French, and German. The agent must cross-reference this registry during every `/ingest` operation to map foreign script, kunyas (nicknames), acronyms, and transliteration variants to a single **Canonical English Title** in `wiki/`. Automated enrichment (`scripts/enrich_graph.py`) synchronizes this registry into ArcadeDB's `AliasLookup` store and Neo4j search keys.

---

## 1. Acting Entities (`wiki/actors/`) — Armed Groups, State Forces, Political Bodies, Civil Society & Leaders

| Term / Primary Acronym | Canonical Entity / Concept | Aliases, Arabic Script & Transliterations | Context / ACLED Classification & Disambiguation |
| :--- | :--- | :--- | :--- |
| **SAF** | [[Sudanese Armed Forces]] | `SAF`, `Sudanese Army`, `القوات المسلحة السودانية`, `الجيش السوداني`, `Al-Quwwat al-Musallaha al-Sudaniyya`, `Al-Jaysh al-Sudani` | `actor` (`state_force` \| `ACLED Inter: 1`). Official military of Sudan commanded by [[Abdel Fattah al-Burhan]]. |
| **RSF** | [[Rapid Support Forces]] | `RSF`, `قوات الدعم السريع`, `الدعم السريع`, `Quwwat ad-Da'm as-Sari'`, `Rapid Support Militia` | `actor` (`armed_group` \| `ACLED Inter: 3`). Paramilitary force commanded by [[Mohamed Hamdan Dagalo]]. |
| **Hemedti** | [[Mohamed Hamdan Dagalo]] | `Hemedti`, `Hemetti`, `Hamdan Dagalo`, `حميدتي`, `محمد حمدان دقلو`, `Gen. Dagalo` | `actor` (`person`). Commander of the [[Rapid Support Forces]]. Never create a separate note under the nickname "Hemedti". |
| **Al-Burhan** | [[Abdel Fattah al-Burhan]] | `Al-Burhan`, `Burhan`, `البرهان`, `عبد الفتاح البرهان`, `Gen. Abdel Fattah al-Burhan` | `actor` (`person`). Commander-in-Chief of [[Sudanese Armed Forces]] and President of the [[Transitional Sovereignty Council]]. |
| **TSC** | [[Transitional Sovereignty Council]] | `TSC`, `Sovereignty Council`, `مجلس السيادة الانتقالي`, `Majlis al-Siyada` | `actor` (`political_body`). Executive state body currently based in [[Port Sudan]]. |
| **JDF** | [[Joint Darfur Force]] | `Joint Force`, `Darfur Joint Force`, `القوة المشتركة`, `القوة المشتركة لحركات الكفاح المسلح`, `Joint Force of Armed Struggle Movements` | `actor` (`armed_group`). Coalition of Darfuri Juba Peace Agreement signatory movements (including SLM-Minawi and JEM-Gibril) allied with [[Sudanese Armed Forces]]. |
| **SLM-MM** | [[Sudan Liberation Movement (Minni Minawi)]] | `SLM-Minawi`, `SLA-MM`, `SLA-Minawi`, `حركة تحرير السودان - مناوي` | `actor` (`armed_group`). Darfuri armed movement led by [[Minni Arko Minawi]], core component of the [[Joint Darfur Force]]. |
| **JEM** | [[Justice and Equality Movement]] | `JEM`, `JEM-Gibril`, `حركة العدل والمساواة`, `Justice and Equality Movement (Gibril Ibrahim)` | `actor` (`armed_group`). Darfuri armed movement led by [[Gibril Ibrahim]], aligned with [[Sudanese Armed Forces]] and [[Joint Darfur Force]]. |
| **SLA-AW** | [[Sudan Liberation Movement (Abdul Wahid)]] | `SLA-AW`, `SLM-AW`, `SLA-Abdul Wahid`, `حركة تحرير السودان - عبد الواحد النور` | `actor` (`armed_group` \| `ACLED Inter: 2`). Non-signatory rebel movement led by [[Abdul Wahid al-Nur]] controlling territory in [[Jebel Marra]]. |
| **SPLM-N (al-Hilu)** | [[SPLM-N (al-Hilu)]] | `SPLM-N`, `SPLM-N al-Hilu`, `الحركة الشعبية لتحرير السودان - شمال (الحلو)`, `Sudan People's Liberation Movement-North (Abdelaziz al-Hilu)` | `actor` (`armed_group` \| `ACLED Inter: 2`). Armed movement led by [[Abdelaziz al-Hilu]] operating in [[South Kordofan]] and [[Blue Nile]]. |
| **SSF** | [[Sudan Shield Forces]] | `Sudan Shield`, `قوات درع السودان`, `Quwwat Dir' al-Sudan` | `actor` (`armed_group` \| `ACLED Inter: 3`). Central Sudan militia founded by [[Abu Aqla Keikel]]. |
| **Al-Baraa Brigade** | [[Al-Baraa Ibn Malik Brigade]] | `Al-Baraa Ibn Malik`, `كتيبة البراء بن مالك`, `Katibat al-Bara' ibn Malik` | `actor` (`armed_group` \| `ACLED Inter: 3`). Islamist auxiliary battalion fighting alongside [[Sudanese Armed Forces]]. |
| **GIS** | [[General Intelligence Service (Sudan)]] | `GIS`, `المخابرات العامة`, `جهاز المخابرات العامة`, `NISS (former)` | `actor` (`state_force` \| `ACLED Inter: 1`). State intelligence agency of Sudan. |
| **ERR** | [[Emergency Response Rooms]] | `ERR`, `ERRs`, `غرف الطوارئ`, `Ghuraf al-Tawari'`, `Sudan Emergency Response Rooms` | `actor` (`civil_society` \| `ACLED Inter: 7`). Grassroots civilian humanitarian and medical responder network across Sudan. |
| **Resistance Committees** | [[Sudanese Resistance Committees]] | `Resistance Committees`, `لجان المقاومة`, `Lijan al-Muqawama` | `actor` (`civil_society` \| `ACLED Inter: 6/7`). Neighborhood-level pro-democracy and civilian coordination networks. |
| **Taqaddum** | [[Taqaddum Coalition]] | `Taqaddum`, `Tagadum`, `تقدم`, `تنسيقية القوى الديمقراطية المدنية`, `Civil Democratic Forces Alliance` | `actor` (`political_body`). Civilian political coalition chaired by former Prime Minister [[Abdalla Hamdok]]. |
| **FFC** | [[Forces of Freedom and Change]] | `FFC`, `قوى الحرية والتغيير`, `Quwwat al-Hurriyya wa-l-Taghyir` | `actor` (`political_body`). Civilian political coalition (note splits between FFC-Central Council and FFC-Democratic Block). |
| **UN News** | [[UN News]] | `UN News`, `United Nations News`, `UN News Centre`, `أخبار الأمم المتحدة` | `actor` (`media_source` \| `Admiralty: A`). Official United Nations news outlet publishing verified reports from UN agencies and missions. |
| **OHCHR** | [[OHCHR]] | `OHCHR`, `UN Human Rights Office`, `Office of the United Nations High Commissioner for Human Rights`, `المفوضية السامية للأمم المتحدة لحقوق الإنسان` | `actor` (`political_body`). Primary UN human rights monitoring agency led by High Commissioner [[Volker Türk]]. |
| **UNISFA** | [[UNISFA]] | `UNISFA`, `United Nations Interim Security Force for Abyei`, `قوة الأمم المتحدة الأمنية المؤقتة لأبيي` | `actor` (`state_force` \| `ACLED Inter: 8`). UN peacekeeping mission mandated to protect demilitarized [[Abyei]] (`SD18001`). |
| **Volker Türk** | [[Volker Türk]] | `Volker Türk`, `Volker Turk`, `فولكر تورك`, `UN High Commissioner for Human Rights Volker Türk` | `actor` (`person`). UN High Commissioner for Human Rights ([[OHCHR]]). |
| **Seif Magango** | [[Seif Magango]] | `Seif Magango`, `سيف ماغانغو`, `OHCHR Spokesperson Seif Magango` | `actor` (`person`). Spokesperson for the UN High Commissioner for Human Rights ([[OHCHR]]). |
| **Muhammad Farooq** | [[Muhammad Farooq]] | `Muhammad Farooq`, `Lt. Col. Muhammad Farooq`, `Lieutenant Colonel Muhammad Farooq` | `actor` (`person`). Lieutenant Colonel commanding the Pakistani peacekeeping battalion of [[UNISFA]] in [[Abyei]]. |
| **Adebowale Ajabge** | [[Adebowale Ajabge]] | `Adebowale Ajabge`, `Brig. Gen. Adebowale Ajabge`, `Brigadier General Adebowale Ajabge` | `actor` (`person`). Brigadier General serving as Acting Force Commander of [[UNISFA]] in [[Abyei]]. |
| **Angelina Musa Diaw** | [[Angelina Musa Diaw]] | `Angelina Musa Diaw` | `actor` (`person`). Civilian market trader and survivor of the 19 October 2026 Amiet Market drone strike in [[Abyei]]. |
| **UN** | [[United Nations]] | `United Nations`, `UN`, `UNO`, `الأمم المتحدة`, `منظمة الأمم المتحدة`, `UN Secretariat` | `actor` (`political_body` \| `ACLED Inter: 8`). Intergovernmental organization led by Secretary-General [[António Guterres]], overseeing [[UNISFA]] and [[OHCHR]]. |
| **UNSG Spokesperson Office** | [[Office of the Spokesperson for the Secretary-General]] | `Office of the Spokesperson for the Secretary-General`, `UN Spokesperson's Office`, `OSSG`, `Spokesperson for the Secretary-General`, `مكتب المتحدث الرسمي باسم الأمين العام للأمم المتحدة` | `actor` (`media_source` \| `Admiralty: A`). Official diplomatic press office of the [[United Nations]] Secretary-General headed by [[Stéphane Dujarric]]. |
| **Stéphane Dujarric** | [[Stéphane Dujarric]] | `Stéphane Dujarric`, `Stephane Dujarric`, `Spokesperson for the Secretary-General Stéphane Dujarric`, `ستيفان دوجاريك` | `actor` (`person`). Spokesperson for the [[United Nations]] Secretary-General ([[Office of the Spokesperson for the Secretary-General]]). |
| **António Guterres** | [[António Guterres]] | `António Guterres`, `Antonio Guterres`, `UN Secretary-General António Guterres`, `Secretary-General Guterres`, `أنطونيو غوتيريش` | `actor` (`person`). Ninth Secretary-General of the [[United Nations]]. |

---

## 2. Geopolitical Locations (`wiki/locations/`) — Sudan 18 States (`ADM1` UN OCHA P-Codes) & Major Hubs

| UN OCHA P-Code | Canonical Location Node | Aliases, Arabic Script & Transliteration Variants | Admin Level & Geopolitical Context |
| :--- | :--- | :--- | :--- |
| **SD01** | [[Khartoum State]] | `Khartoum`, `Wilayat al-Khartum`, `ولاية الخرطوم`, `Al-Khartum` | `state_adm1` (`ADM1`). Capital state comprising the tripartite metropolis: [[Khartoum]], [[Omdurman]], and [[Bahri]]. |
| **SD01001** | [[Khartoum]] | `Khartoum City`, `الخرطوم`, `Al-Khartum` | `city_town` (`ADM2/City`). National capital south of the Blue and White Nile confluence. |
| **SD01002** | [[Omdurman]] | `Omdurman`, `Umm Durman`, `أم درمان`, `امدرمان` | `city_town` (`ADM2/City`). Western bank of the Nile across from [[Khartoum]] and [[Bahri]]. |
| **SD01003** | [[Bahri]] | `Khartoum North`, `Bahri`, `Al-Khartum Bahri`, `بحري`, `الخرطوم بحري` | `city_town` (`ADM2/City`). Northern industrial and residential city of Greater Khartoum. |
| **SD02** | [[North Darfur]] | `North Darfur State`, `Shamal Darfur`, `شمال دارفور`, `ولاية شمال دارفور` | `state_adm1` (`ADM1`). Capital: [[El Fasher]]. |
| **SD02001** | [[El Fasher]] | `Al-Fashir`, `El-Fasher`, `Fasher`, `الفاشر` | `city_town` (`ADM2/City`). Capital of [[North Darfur]]; adjacent to [[Zamzam IDP Camp]]. |
| **SD03** | [[South Darfur]] | `South Darfur State`, `Janub Darfur`, `جنوب دارفور` | `state_adm1` (`ADM1`). Capital: [[Nyala]] (`نيالا`). |
| **SD04** | [[Central Darfur]] | `Central Darfur State`, `Wasat Darfur`, `وسط دارفور` | `state_adm1` (`ADM1`). Capital: [[Zalingei]] (`زالنجي`); includes [[Jebel Marra]] (`جبل مرة`). |
| **SD05** | [[East Darfur]] | `East Darfur State`, `Sharq Darfur`, `شرق دارفور` | `state_adm1` (`ADM1`). Capital: [[Ed Daein]] (`الضعين`, `Al-Du'ayn`). |
| **SD06** | [[West Darfur]] | `West Darfur State`, `Gharb Darfur`, `غرب دارفور` | `state_adm1` (`ADM1`). Capital: [[El Geneina]] (`الجنينة`, `Al-Junaynah`); borders Chad via [[Adre Border Crossing]]. |
| **SD07** | [[Northern State]] | `Northern`, `Ash-Shamaliyya`, `الشمالية`, `الولاية الشمالية` | `state_adm1` (`ADM1`). Capital: [[Dongola]] (`دنقلا`); includes [[Merowe]] (`مروي`). |
| **SD08** | [[River Nile State]] | `River Nile`, `Nahr an-Nil`, `نهر النيل`, `ولاية نهر النيل` | `state_adm1` (`ADM1`). Capital: [[Ed Damer]] (`الدامر`); major rail/military hub: [[Atbara]] (`عطبرة`) and [[Shendi]] (`شندي`). |
| **SD09** | [[Kassala State]] | `Kassala`, `كسلا`, `ولاية كسلا` | `state_adm1` (`ADM1`). Eastern state bordering Eritrea; capital: [[Kassala]]. |
| **SD10** | [[Red Sea State]] | `Red Sea`, `Al-Bahr al-Ahmar`, `البحر الأحمر`, `ولاية البحر الأحمر` | `state_adm1` (`ADM1`). Capital: [[Port Sudan]] (`بورتسودان`, `Bur Sudan`), wartime seat of the [[Transitional Sovereignty Council]]. |
| **SD11** | [[South Kordofan]] | `South Kordofan State`, `Janub Kurdufan`, `جنوب كردفان` | `state_adm1` (`ADM1`). Capital: [[Kadugli]] (`كادوقلي`); includes Nuba Mountains. |
| **SD12** | [[Gedaref State]] | `Gedaref`, `Al-Qadarif`, `Gadaref`, `القضارف`, `ولاية القضارف` | `state_adm1` (`ADM1`). Eastern agricultural state bordering Ethiopia. |
| **SD13** | [[North Kordofan]] | `North Kordofan State`, `Shamal Kurdufan`, `شمال كردفان` | `state_adm1` (`ADM1`). Capital and strategic logistics hub: [[El Obeid]] (`الأبيض`, `Al-Ubayyid`). |
| **SD14** | [[Sennar State]] | `Sennar`, `Sinnar`, `سنار`, `ولاية سنار` | `state_adm1` (`ADM1`). Capital: [[Sinjah]] (`سنجة`, `Sinja`); major city: [[Sennar]]. |
| **SD15** | [[Al Jazirah]] | `Gezira`, `Al-Jazira`, `Gezira State`, `الجزيرة`, `ولاية الجزيرة` | `state_adm1` (`ADM1`). Central agricultural heartland; capital: [[Wad Madani]] (`ود مدني`, `Medani`). |
| **SD16** | [[White Nile State]] | `White Nile`, `An-Nil al-Abyad`, `النيل الأبيض`, `ولاية النيل الأبيض` | `state_adm1` (`ADM1`). Capital: [[Rabak]] (`ربك`); major hub: [[Kosti]] (`كوستي`). |
| **SD17** | [[Blue Nile State]] | `Blue Nile`, `An-Nil al-Azraq`, `النيل الأزرق`, `إقليم النيل الأزرق` | `state_adm1` (`ADM1`). Capital: [[Ed Damazin]] (`الدمازين`, `Damazin`); includes Abu Shendi and Um Darfa. |
| **SD18** | [[West Kordofan]] | `West Kordofan State`, `Gharb Kurdufan`, `غرب كردفان` | `state_adm1` (`ADM1`). Capital: [[El Fula]] (`الفولة`); major hubs: [[Babanusa]] (`بابنوسة`), Dibab, Ghubeish, and El Nuhud. |
| **SD18001** | [[Abyei]] | `Abyei Area`, `Abyei PCA Area`, `أبيي`, `منطقة أبيي`, `Amiet Market`, `Todach` | `locality_adm2` (`ADM2/Special Area`). Disputed, oil-rich demilitarized border region patrolled by [[UNISFA]]; includes Amiet Market and Todach. |
