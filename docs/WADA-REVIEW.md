# WADA 2026 금지목록 추출본 검토 기록

대상: [data/wada/prohibited_list_2026.json](../data/wada/prohibited_list_2026.json)
만든 방법: [analysis/wada_extract.py](../analysis/wada_extract.py)(원문 PDF 자동 추출) + [analysis/wada_manual_2026.yaml](../analysis/wada_manual_2026.yaml)(손 보정)
원문: WADA 2026 Prohibited List(영문), sha256 `f0b3fcb0dc48477868983eaddac08c132b5c079d941eaa8d40aa6ff9064ece5a`

**상태: `reviewed: false`.** 아래 1~2는 AI가 한 검토입니다. AI가 만든 추출본을 AI가 검토했으므로 독립 검토가 아닙니다. 사람 검토자가 3의 표본을 원문과 대조하고 4에 서명해야 `reviewed: true`로 바꿉니다. 그전에는 시범 서버(`DEMO_MODE=0`)가 시작되지 않습니다(G2).

## 1. 1차 독립 검토에서 나온 결함 (2026-10-12)

첫 추출본(414항목)을 원문 PDF·원문 INDEX와 대조해 28건을 찾았습니다. 그중 앱이 실제보다 덜 엄격하게 보여주는 결함이 있었습니다.

| 심각도 | 결함 | 영향 | 조치 |
|---|---|---|---|
| A1 | 금지방법 M1–M3이 S5 "예외"로 들어감 | perfluorochemicals·efaproxiral·voxelotor·gene silencing이 "조건부"로 나옴(원문은 상시 금지) | M 섹션 제목 인식 수정, M1–M3은 손 보정 항목으로 |
| A2 | "e.g." 앞 이름 버림, 숫자로 시작하는 이름, 글머리 뒤 문단이 붙음, `[e.g. …]`, "and its derivatives" 꼬리, 첫 괄호에서 이름 자름, 제로폭 공백 | Cathinone·Prolintane·DMBA 계열·BPC-157·DNP·gonadorelin·kisspeptin·GH·IGF-1·insulin·fentanyl·enobosarm·LGD-4033·marijuana·THC·MDMA·elacestrant 등이 "확인 필요"로 나옴 | 추출기 수정 + S0 손 보정 |
| A3 | P1 종목 6/8, 경기기간 외 금지(*) 표시 없음 / S3·S5·S9 NOTE 누락 | 역도 선수 판정에는 영향 없음 | 손 보정(종목 8개, * 3개, 섹션 조건) |
| B·C | 조건 없는 예외가 "조건부"로, 표기 깨짐, 하위 분류 순서, 조건 문장 잘림 | 보수적이거나 표시만 틀림 | 대부분 수정. 조건 없는 예외(drospirenone 등)는 "조건부" 유지(보수적) |

## 2. 수정 후 확인한 것

| 확인 | 결과 |
|---|---|
| 원문 sha256 | 일치 |
| 항목 수 | 443 (자동 421 + 손 보정 22). 섹션별 수는 JSON의 `counts` |
| 원문 INDEX 540개 표제어 | 방법 설명 단어 등 22개(사유를 `index_not_substances`에 기록)를 뺀 518개가 **모두 조회되고, 표제어 쪽의 섹션과 같은 섹션으로 판정됨** |
| 상시 금지 섹션(S0–S5, M) 표제어 | 경기기간 외 조회에서 모두 "금지". 예외는 원문에 이름이 적힌 예외·기준치 13개뿐 |
| S5 예외 | 정확히 5개(drospirenone, pamabrom, dorzolamide, brinzolamide, felypressin) |
| 회귀 테스트 | [backend/tests/test_wada_list.py](../backend/tests/test_wada_list.py) 76개 통과. 첫 추출본에 돌리면 36개가 실패해서, 결함을 실제로 잡는다는 것을 확인함 |

남은 한계
- WADA 목록은 닫힌 목록이 아닙니다("including, but not limited to", "similar chemical structure"). 목록에 없는 이름은 "허용"이 아니라 "확인 필요"로 나옵니다.
- 조건 없는 예외(drospirenone, pamabrom, clonidine, guanfacine)는 "조건에 따라 금지 아닐 수 있음"으로 나옵니다. 원문보다 엄격한 쪽입니다.
- 혈장 증량제(albumin, mannitol 등)는 "정맥 투여" 조건과 관계없이 "금지"로 나옵니다. 보수적인 쪽입니다.

## 3. 사람 검토 표본

원문 PDF(위 sha256)를 옆에 두고 각 줄의 이름·분류·조건이 원문과 같은지 확인한 뒤 ☐를 ☑로 바꿉니다. 하나라도 다르면 표시하고 서명하지 않습니다.

### A. 예외·기준치·모니터링 전부 (32개)

덜 엄격한 판정으로 이어지는 항목이라 전부 봅니다.

| 섹션 | 이름 | 동의어 | 분류 | 쪽 | 조건 | 확인 |
|---|---|---|---|---|---|---|
| S3 | salbutamol |  | exception | 9 | Inhaled salbutamol: maximum 1600 micrograms over 24 hours in divided doses not to exceed 6… | ☐ |
| S3 | formoterol |  | exception | 9 | Inhaled formoterol: maximum delivered dose of 54 micrograms over 24 hours in divided doses… | ☐ |
| S3 | salmeterol |  | exception | 9 | Inhaled salmeterol: maximum 200 micrograms over 24 hours in divided doses not to exceed 10… | ☐ |
| S3 | vilanterol |  | exception | 9 | Inhaled vilanterol: maximum 25 micrograms over 24 hours | ☐ |
| S5 | Drospirenone |  | exception | 12 | Drospirenone; pamabrom; and topical ophthalmic administration of carbonic anhydrase inhibi… | ☐ |
| S5 | pamabrom |  | exception | 12 | Drospirenone; pamabrom; and topical ophthalmic administration of carbonic anhydrase inhibi… | ☐ |
| S5 | dorzolamide |  | exception | 12 | Drospirenone; pamabrom; and topical ophthalmic administration of carbonic anhydrase inhibi… | ☐ |
| S5 | brinzolamide |  | exception | 12 | Drospirenone; pamabrom; and topical ophthalmic administration of carbonic anhydrase inhibi… | ☐ |
| S5 | felypressin |  | exception | 12 | Local administration of felypressin in dental anaesthesia | ☐ |
| S6 S6.B | Cathine |  | threshold | 16 | Cathine (d-norpseudoephedrine) and its l-isomer: Prohibited when its concentration in urin… | ☐ |
| S6 S6.B | Ephedrine |  | threshold | 16 | Ephedrine and methylephedrine: Prohibited when the concentration of either in urine is gre… | ☐ |
| S6 S6.B | Methylephedrine |  | threshold | 16 | Ephedrine and methylephedrine: Prohibited when the concentration of either in urine is gre… | ☐ |
| S6 S6.B | Pseudoephedrine |  | threshold | 16 | Pseudoephedrine: Prohibited when its concentration in urine is greater than 150 micrograms… | ☐ |
| S6 S6.B | Clonidine |  | exception | 16 | Clonidine, guanfacine | ☐ |
| S6 S6.B | guanfacine |  | exception | 16 | Clonidine, guanfacine | ☐ |
| S6 S6.B | brimonidine |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | clonazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | fenoxazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | indanazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | naphazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | oxymetazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | tetryzoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | tramazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S6 S6.B | xylometazoline |  | exception | 16 | Imidazoline derivatives for dermatological, nasal, ophthalmic or otic use (e.g. brimonidin… | ☐ |
| S8 | Cannabidiol |  | exception | 18 | Cannabidiol | ☐ |
| S6 | Bupropion |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |
| S6 | caffeine |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |
| S6 | nicotine |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |
| S6 | phenylephrine |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |
| S6 | phenylpropanolamine |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |
| S6 | pipradrol |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |
| S6 | synephrine |  | exception |  | Bupropion, caffeine, nicotine, phenylephrine, phenylpropanolamine, pipradrol, and synephri… | ☐ |

### B. 손 보정 항목 전부 (22개)

자동 추출이 아니라 손으로 적은 항목(S0, M1–M3, S1 에스터)입니다.

| 섹션 | 이름 | 동의어 | 분류 | 쪽 | 조건 | 확인 |
|---|---|---|---|---|---|---|
| S0 | BPC-157 |  | prohibited | 4 |  | ☐ |
| S0 | 2,4-Dinitrophenol | DNP | prohibited | 4 |  | ☐ |
| S0 | Ryanodine receptor-1-calstabin complex stabilizers |  | prohibited | 4 |  | ☐ |
| S0 | S-107 |  | prohibited | 4 |  | ☐ |
| S0 | S48168 | ARM210 | prohibited | 4 |  | ☐ |
| S0 | Troponin activators |  | prohibited | 4 |  | ☐ |
| S0 | Reldesemtiv |  | prohibited | 4 |  | ☐ |
| S0 | Tirasemtiv |  | prohibited | 4 |  | ☐ |
| S0 | Non-approved substances | designer drugs, substances approved only for veterinary use | prohibited | 4 | 어느 섹션에도 없고 사람 치료용으로 승인되지 않은 약리 물질(임상 전·임상 중·중단된 약, 디자이너 약물, 동물용 전용 약)은 상시 금지 | ☐ |
| S1 S1.1 | Esters of anabolic androgenic steroids |  | prohibited | 6 |  | ☐ |
| M1 M1.1 | Blood transfusion | blood doping, autologous blood transfusion, homologous blood transfusion, red blood cell products | prohibited | 13 | 자가·동종·이종 혈액 또는 적혈구 제제를 순환계에 투여·재주입하는 것은 상시 금지 | ☐ |
| M1 M1.1 | Withdrawal of blood | apheresis, Blood withdrawal | prohibited | 13 | 혈액·혈액 성분 채취 금지. 단 1) 의료 검사·도핑검사 목적 2) 공인 기관 헌혈은 제외 | ☐ |
| M1 M1.2 | Perfluorochemicals |  | prohibited | 13 |  | ☐ |
| M1 M1.2 | Efaproxiral | RSR13 | prohibited | 13 |  | ☐ |
| M1 M1.2 | Voxelotor |  | prohibited | 13 |  | ☐ |
| M1 M1.2 | Modified haemoglobin products | haemoglobin-based blood substitutes, microencapsulated haemoglobin products | prohibited | 13 | 산소 운반 인위적 향상. 보충 산소 흡입은 제외 | ☐ |
| M1 M1.3 | Intravascular manipulation of blood | Blood manipulation | prohibited | 13 | 혈액·혈액 성분을 물리적·화학적으로 혈관 안에서 조작하는 모든 방법 | ☐ |
| M1 M1.4 | Carbon monoxide re-breathing | Carbon monoxide, Re-breathing systems or equipment to deliver carbon monoxide | prohibited | 13 | 일산화탄소 재호흡 장치 사용 금지. 의료·과학 전문가 감독 아래 진단 목적이면 제외 | ☐ |
| M2 M2.1 | Sample tampering | Tampering, sample substitution, urine substitution, sample adulteration | prohibited | 13 | 도핑검사 시료의 바꿔치기·변조 시도 포함 상시 금지 | ☐ |
| M2 M2.2 | Intravenous infusion | Infusions, Intravenous infusions/injections, intravenous injection, IV infusion | prohibited | 13 | 12시간 동안 합계 100 mL를 넘는 정맥 수액·주사는 상시 금지. 병원 치료·수술·임상 진단 검사 중 정당하게 받은 경우는 제외. 필요하면 TUE | ☐ |
| M3 M3.1 | Gene doping | gene editing, gene silencing, gene transfer | prohibited | 14 | 유전체 서열·유전자 발현을 바꿀 수 있는 핵산·핵산 유사체 사용 금지 | ☐ |
| M3 M3.2 | Cell doping | genetically modified cells | prohibited | 14 | 정상 또는 유전자 변형 세포·세포 성분(핵, 미토콘드리아·리보솜 등 세포 소기관) 사용 금지 | ☐ |

### C. 섹션별 무작위 표본 (48개, 섹션당 최대 5개, seed 2026)

| 섹션 | 이름 | 동의어 | 분류 | 쪽 | 조건 | 확인 |
|---|---|---|---|---|---|---|
| S1 S1.1 | Androst-4-ene-3,11,17-trione | 11-ketoandrostenedione, adrenosterone | prohibited | 5 |  | ☐ |
| S1 S1.1 | Metenolone |  | prohibited | 6 |  | ☐ |
| S1 S1.1 | Tetrahydrogestrinone | 17-hydroxy-18ahomo-19-nor-17ɑ-pregna-4,9,11-trien-3-one | prohibited | 6 |  | ☐ |
| S1 S1.1 | Tibolone |  | prohibited | 6 |  | ☐ |
| S1 S1.1 | 19-Norandrostenediol | estr-4-ene-3,17-diol | prohibited | 5 |  | ☐ |
| S2 S2.2.1 | luteinizing hormone |  | prohibited | 8 |  | ☐ |
| S2 S2.3 | Platelet-derived growth factor | PDGF | prohibited | 8 |  | ☐ |
| S2 S2.3 | Vascular endothelial growth factor | VEGF | prohibited | 8 |  | ☐ |
| S2 S2.2.4 | GH-releasing peptides | GHRPs | prohibited | 8 | GH-releasing peptides (GHRPs) [e.g. alexamorelin, examorelin (hexarelin), GHRP-1, GHRP-2 (… | ☐ |
| S2 S2.2.4 | tesamorelin |  | prohibited | 8 | growth hormone-releasing hormone (GHRH) and its analogues (e.g. CJC-1293, CJC-1295, sermor… | ☐ |
| S3 | Tretoquinol | trimetoquinol | prohibited | 9 |  | ☐ |
| S3 | Salbutamol |  | prohibited | 9 |  | ☐ |
| S3 | Reproterol |  | prohibited | 9 |  | ☐ |
| S3 | Terbutaline |  | prohibited | 9 |  | ☐ |
| S3 | Procaterol |  | prohibited | 9 |  | ☐ |
| S4 S4.4.2 | Insulins | insulin, insulin-mimetics | prohibited | 11 |  | ☐ |
| S4 S4.4.2 | S519 |  | prohibited | 11 |  | ☐ |
| S4 S4.3 | stamulumab |  | prohibited | 11 | Myostatin- or precursor-neutralizing antibodies (e.g. apitegromab, domagrozumab, landogroz… | ☐ |
| S4 S4.3 | Anti-activin receptor IIB antibodies |  | prohibited | 11 | Anti-activin receptor IIB antibodies (e.g. bimagrumab) | ☐ |
| S4 S4.2 | Clomifene |  | prohibited | 10 |  | ☐ |
| S5 | Diuretics |  | prohibited | 12 | Diuretics such as: Acetazolamide; amiloride; bumetanide; canrenone; chlortalidone; etacryn… | ☐ |
| S5 | mozavaptan |  | prohibited | 12 | Vaptans, e.g. conivaptan, mozavaptan, tolvaptan | ☐ |
| S5 | amiloride |  | prohibited | 12 | Diuretics such as: Acetazolamide; amiloride; bumetanide; canrenone; chlortalidone; etacryn… | ☐ |
| S5 | bumetanide |  | prohibited | 12 | Diuretics such as: Acetazolamide; amiloride; bumetanide; canrenone; chlortalidone; etacryn… | ☐ |
| S5 | metolazone |  | prohibited | 12 | Diuretics such as: Acetazolamide; amiloride; bumetanide; canrenone; chlortalidone; etacryn… | ☐ |
| S6 S6.A | Fencamine |  | prohibited | 15 |  | ☐ |
| S6 S6.B | Meclofenoxate |  | prohibited | 16 |  | ☐ |
| S6 S6.A | Amfepramone |  | prohibited | 15 |  | ☐ |
| S6 S6.B | Nikethamide |  | prohibited | 16 |  | ☐ |
| S6 S6.B | mephedrone |  | prohibited | 16 | Cathinone and its analogues, e.g. mephedrone, methedrone, and ɑ -pyrrolidinovalerophenone | ☐ |
| S7 | Fentanyl |  | prohibited | 17 |  | ☐ |
| S7 | Morphine |  | prohibited | 17 |  | ☐ |
| S7 | Hydromorphone |  | prohibited | 17 |  | ☐ |
| S7 | Methadone |  | prohibited | 17 |  | ☐ |
| S7 | Oxymorphone |  | prohibited | 17 |  | ☐ |
| S8 | Natural and synthetic tetrahydrocannabinols | THCs, Tetrahydrocannabinols, tetrahydrocannabinol, THC | prohibited | 18 |  | ☐ |
| S8 | cannabis and cannabis products | hashish, marijuana, cannabis, marihuana | prohibited | 18 |  | ☐ |
| S8 | Synthetic cannabinoids that mimic the effects of THC |  | prohibited | 18 |  | ☐ |
| S9 | Budesonide |  | prohibited | 19 |  | ☐ |
| S9 | Fluocortolone |  | prohibited | 19 |  | ☐ |
| S9 | Prednisone |  | prohibited | 19 |  | ☐ |
| S9 | Cortisone |  | prohibited | 19 |  | ☐ |
| S9 | Mometasone |  | prohibited | 19 |  | ☐ |
| P1 | Nebivolol |  | prohibited | 20 |  | ☐ |
| P1 | Bisoprolol |  | prohibited | 20 |  | ☐ |
| P1 | Esmolol |  | prohibited | 20 |  | ☐ |
| P1 | Acebutolol |  | prohibited | 20 |  | ☐ |
| P1 | Metipranolol |  | prohibited | 20 |  | ☐ |

## 4. 서명

| 검토자 | 소속·역할 | 날짜 | 표본 결과 | 서명 |
|---|---|---|---|---|
| | | | ☐ 모두 일치 / ☐ 불일치 있음(위 표에 표시) | |

서명이 끝나면 `data/wada/prohibited_list_2026.json`의 `reviewed`를 `true`로 바꾸고, 이 문서와 함께 커밋합니다. 금지목록이 바뀌는 해(2027 목록)에는 추출과 이 검토를 다시 합니다.
