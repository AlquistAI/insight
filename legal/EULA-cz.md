# Alquist Insight — Licenční smlouva s koncovým uživatelem a podmínky poskytování služby

**Verze 1.0 — účinná od 1. října 2026**

> **Jazykové znění.** Tento český text je závazným zněním pro spotřebitele
> s obvyklým bydlištěm v České republice a pro Zákazníky se sídlem v České
> republice. V ostatních případech platí anglické znění (`EULA.md`).
> Viz článek 9.5.

---

## 0. Smluvní strany a struktura této Smlouvy

**Poskytovatel / Licencor:**
České vysoké učení technické v Praze, Český institut informatiky, robotiky
a kybernetiky (CIIRC), Jugoslávských partyzánů 1580/3, 160 00 Praha 6, Česká
republika, IČO 68407700, tj. strana, která provozuje server Alquist Insight
a vkládá obsah pro Zákazníky (dále jen „**Poskytovatel**“, „my“).

Tato Smlouva má tři části:

- **Část A — Obecná ustanovení**, platná pro všechny.
- **Část B — Ustanovení pro Zákazníka**, platná pro organizaci, která si Službu
  předplácí a jejíž obsah je vkládán, a pro její administrátory užívající
  Administrátorskou konzoli (dále jen „**Zákazník**“).
- **Část C — Ustanovení pro Koncového uživatele**, platná pro každou fyzickou
  osobu, která pokládá dotazy prostřednictvím anonymního Klienta (dále jen
  „**Koncový uživatel**“).

Informace o ochraně osobních údajů požadované články 13 a 14 nařízení (EU)
2016/679 (dále jen „**GDPR**“) jsou uvedeny samostatně v dokumentu
`PRIVACY-NOTICE-cz.md`, který tvoří nedílnou součást této Smlouvy.

**Zdrojový kód** aplikace Alquist Insight je zveřejněn jako otevřený software
pod licencí MIT (viz `LICENSE`). **Tato Smlouva neomezuje práva udělená licencí
MIT ve vztahu ke zdrojovému kódu.** Upravuje výhradně užívání hostované služby
Alquist Insight provozované Poskytovatelem (dále jen „**Služba**“). Kdokoli, kdo
si kód z veřejného repozitáře provozuje sám, tak činí pouze na základě licence
MIT a není stranou této Smlouvy.

---

# Část A — Obecná ustanovení

## 1. Definice

1.1 **Služba** — hostovaný systém Alquist Insight provozovaný Poskytovatelem,
zahrnující Server, Administrátorskou konzoli a Klienta.

1.2 **Server** — backend založený na generování s využitím vyhledávání
(„RAG“ — retrieval-augmented generation), hostovaný na infrastruktuře
poskytované společností Hetzner Online GmbH v Evropské unii.

1.3 **Administrátorská konzole** — autentizované rozhraní, jehož
prostřednictvím je obsah Zákazníka vkládán, spravován a sledován. Přístup je
zajištěn systémem správy identit a přístupů Keycloak.

1.4 **Klient** — anonymní rozhraní pro koncové uživatele umožňující pokládat
dotazy k vloženému obsahu. Nevyžaduje účet ani přihlášení.

1.5 **Obsah Zákazníka** — dokumenty, data a další materiály poskytnuté
Zákazníkem nebo v jeho zastoupení a vložené do Serveru.

1.6 **Výstup** — text vytvořený Službou v odpovědi na dotaz, vygenerovaný
s využitím služby velkého jazykového modelu třetí strany, společnosti OpenAI
(viz článek 5).

1.7 **Sezení** — posloupnost dotazů a Výstupů spojených s jedním náhodně
vygenerovaným identifikátorem, užívaným výhradně k udržení kontextu
konverzace. Pro každé nové sezení se **generuje nový identifikátor**; ten není
po skončení sezení uchováván, není opakovaně používán a Poskytovatel jej nemůže
spojit s žádným dřívějším ani pozdějším sezením. Sezení tedy zahrnuje pouze
výměnu, která proběhne, dokud je Klient otevřen v prohlížeči.

## 2. Povaha Služby — transparentnost AI

2.1 **Komunikujete se systémem umělé inteligence.** Výstupy jsou generovány
automaticky velkým jazykovým modelem a před doručením nejsou kontrolovány
člověkem. Toto oznámení se poskytuje v souladu s článkem 50 nařízení (EU)
2024/1689 (dále jen „**akt o AI**“).

2.2 Služba je **záměrně omezena na vymezenou oblast**: odpovídá pouze na
základě Obsahu Zákazníka vloženého pro příslušné nasazení. Pokud dotaz tento
obsah přesahuje, je Služba navržena tak, aby odpověděla, že odpověď nezná,
místo aby spekulovala. Jde o konstrukční cíl, nikoli o záruku.

2.3 Výstupy přesto mohou být **nepřesné, nepodložené či neaktuální** a mohou
obsahovat tvrzení, která nemají oporu v Obsahu Zákazníka. Výstupy jsou
poskytovány pouze pro informaci a **nepředstavují** právní, lékařské,
finanční, daňové, bezpečnostně kritické ani jiné odborné poradenství.
Nespoléhejte na Výstup jako na jediný podklad pro rozhodnutí s právními,
finančními nebo bezpečnostními důsledky; podstatné informace si ověřte
u autoritativního zdroje.

2.4 Služba **není** určena a nesmí být nasazena k žádnému účelu zakázanému
článkem 5 aktu o AI, ani jako bezpečnostní prvek, ani k žádnému vysoce
rizikovému použití podle přílohy III aktu o AI, pokud se strany předem
písemně nedohodly na dalších souvisejících povinnostech.

## 3. Přijatelné užívání

3.1 Je zakázáno:

a) užívat Službu v rozporu s platnými právními předpisy, včetně práva České
   republiky, práva EU a práva místa vašeho bydliště či sídla;
b) vkládat obsah, který je nezákonný, hanlivý, porušující práva třetích osob
   nebo obsahující škodlivý kód;
c) vkládat do dotazů nebo do Obsahu Zákazníka zvláštní kategorie osobních
   údajů (článek 9 GDPR), osobní údaje týkající se odsouzení v trestních
   věcech, údaje o platebních kartách nebo jiné citlivé informace, s výjimkou
   výslovné písemné dohody;
d) pokoušet se obejít řízení přístupu, omezení počtu dotazů nebo oborové
   vymezení Služby, případně získat podkladový model, systémové pokyny nebo
   obsah jiného Zákazníka;
e) užívat automatizované prostředky k dotazování Služby v objemu, který
   zhoršuje její dostupnost pro ostatní, nebo k vytváření konkurenční datové
   sady či modelu systematickým získáváním Výstupů;
f) vydávat se za jinou osobu nebo prezentovat Výstup jako text vytvořený
   člověkem, pokud by to mohlo uvést třetí osobu v omyl.

3.2 Poskytovatel může zcela nebo částečně pozastavit přístup, pokud se
důvodně domnívá, že byl tento článek porušen, nebo pokud další provoz
představuje bezpečnostní, právní nebo integritní riziko. Poskytovatel přístup
obnoví po odstranění příčiny a bez zbytečného odkladu o tom Zákazníka
informuje.

## 4. Práva k duševnímu vlastnictví

4.1 Poskytovatel a jeho licencoři si ponechávají veškerá práva ke Službě
s výjimkou práv ke zdrojovému kódu udělených licencí MIT.

4.2 Zákazník si ponechává veškerá práva k Obsahu Zákazníka. Zákazník uděluje
Poskytovateli nevýhradní bezúplatnou licenci k hostování, zpracování,
indexaci, vytváření embeddingů a přenosu Obsahu Zákazníka výhradně za účelem
provozu a podpory Služby pro tohoto Zákazníka.

4.3 Ve vztahu mezi Poskytovatelem a Zákazníkem si Poskytovatel nečiní nárok na
vlastnictví Výstupů. Poskytovatel **neposkytuje žádnou záruku, že Výstup
nezasahuje do práv třetích osob**, a upozorňuje, že postavení textu
vygenerovaného umělou inteligencí z hlediska autorského práva není v právu EU
ani v českém právu vyjasněno; výstup vytvořený výhradně strojově nemusí být
autorskoprávně chráněn vůbec.

4.4 Označení „Alquist“, „Alquist Insight“ a názvy, loga a známky
Poskytovatele a ČVUT nesmějí být bez předchozího písemného souhlasu užívány
k podpoře nebo propagaci odvozených produktů. Toto omezení je smluvní
a nezávislé na licenci MIT, která rovněž neuděluje žádná práva k ochranným
známkám.

## 5. Služby třetích stran a další zpracovatelé

5.1 Služba předává dotazy a relevantní výňatky z Obsahu Zákazníka do API
velkého jazykového modelu provozovaného společností **OpenAI** za účelem
generování Výstupů. Vaše užívání proto podléhá také příslušným podmínkám
OpenAI. Poskytovatel má sjednány takové podmínky API, podle nichž předaná data
**nejsou užívána k trénování modelů OpenAI**.

5.2 Server je hostován společností **Hetzner Online GmbH** na infrastruktuře
umístěné v Evropské unii. Autentizaci administrátorů zajišťuje **Keycloak**.

5.3 Aktuální seznam dalších zpracovatelů, jejich umístění a uplatněných
záruk pro předávání je veden v dokumentu `PRIVACY-NOTICE-cz.md`. Poskytovatel
uvědomí Zákazníka nejméně 30 dní před přidáním nebo změnou dalšího
zpracovatele; Zákazník může vznést námitku z důvodných příčin souvisejících
s ochranou osobních údajů.

## 6. Ochrana osobních údajů

6.1 Ve vztahu k Obsahu Zákazníka a k dotazům Koncových uživatelů vystupuje
Zákazník jako **správce** a Poskytovatel jako **zpracovatel** ve smyslu
článku 4 GDPR. Strany uzavřou smlouvu o zpracování osobních údajů splňující
článek 28 GDPR; uplatní se `[odkaz na smlouvu o zpracování / příloha 1]`.

6.2 Ve vztahu k vlastním provozním a bezpečnostním záznamům Poskytovatele
a ke správě účtů vystupuje Poskytovatel jako správce.

6.3 Záznamy o Sezení — náhodný identifikátor Sezení, dotazy, Výstupy a časové
údaje — jsou uchovávány na Serveru, aby bylo možné udržet kontext konverzace
a aby Zákazník mohl sledovat provoz a kvalitu. Doby uchování a práva subjektů
údajů jsou uvedeny v dokumentu `PRIVACY-NOTICE-cz.md`.

6.4 Náhodný identifikátor Sezení **není** spojen s jménem, e-mailovou adresou
ani uživatelským účtem a pro **každé sezení je generován nový identifikátor**.
Poskytovatel tedy nedrží k žádné osobě trvalý identifikátor: jediné možné
spojení je mezi dotazy položenými v rámci jednoho sezení prohlížeče a žádná
dvě sezení nelze přiřadit téže osobě. Služba tak již svým návrhem uplatňuje
minimalizaci údajů a omezení uložení podle článku 5 odst. 1 písm. c) a e)
GDPR na architektonické úrovni.

6.5 Bez ohledu na článek 6.4 jsou záznamy o Sezení považovány za **osobní
údaje**, neboť text dotazu může sám o sobě identifikovat určitou osobu.
Poskytovatel na ně proto uplatňuje záruky podle GDPR. Poskytovatel se
nepokouší Koncové uživatele opětovně identifikovat ani spojovat jednotlivá
Sezení a smluvně to zakazuje i Zákazníkovi.

6.6 **Důsledek pro výmaz.** Protože neexistuje žádný trvalý identifikátor,
není Poskytovatel technicky schopen vyhledat, získat ani vymazat záznamy
konkrétní osoby, a není schopen vyhovět žádosti o výmaz, opravu, přístup,
omezení zpracování nebo přenositelnost směřující ke konkrétní osobě (viz
článek 14.5). Jde o inherentní a záměrnou vlastnost architektury, nikoli
o provozní nedostatek. Záznamy o Sezení jsou v celém rozsahu vymazány po
uplynutí doby uchování uvedené v dokumentu `PRIVACY-NOTICE-cz.md`, nebo dříve,
je-li dosaženo objemového limitu podle článku 12.4.

6.7 **Objemový limit.** Uchovávaná data Sezení dále podléhají objemovému
limitu konfigurovatelnému administrátorem Zákazníka, který **nesmí přesáhnout
100 MB**. Při dosažení limitu jsou mazány nejstarší záznamy jako první. Viz
článek 12.4.

## 7. Záruky, odpovědnost a odškodnění

7.1 Není-li výslovně uvedeno jinak, je Služba poskytována **„tak, jak je“**
a Poskytovatel v maximálním rozsahu povoleném právem vylučuje veškeré
předpokládané záruky, včetně vhodnosti pro určitý účel a nepřerušovaného či
bezchybného provozu. Případné závazky dostupnosti jsou uvedeny v `[příloze 2 —
Úrovně služby]`.

7.2 **Žádné ustanovení této Smlouvy neomezuje ani nevylučuje odpovědnost,
kterou podle platného práva nelze omezit ani vyloučit**, včetně odpovědnosti
za smrt nebo újmu na zdraví, za škodu způsobenou úmyslně nebo z hrubé
nedbalosti (§ 2898 zákona č. 89/2012 Sb., občanský zákoník), za porušení
zákonných práv spotřebitele nebo podle směrnice (EU) 2024/2853 o odpovědnosti
za vadné výrobky.

7.3 S výhradou článku 7.2 a pouze ve vztahu k Zákazníkovi je celková
odpovědnost Poskytovatele vzniklá z této Smlouvy v kterémkoli
dvanáctiměsíčním období omezena na vyšší z těchto částek: odměna zaplacená
Zákazníkem v daném období, nebo 10 000 EUR. S výhradou článku 7.2
neodpovídá žádná ze stran za ztrátu zisku, ztrátu příjmů ani za nepřímou či
následnou škodu.

7.4 Zákazník prohlašuje, že má veškerá práva a právní základy nezbytné k tomu,
aby Poskytovatel zpracovával Obsah Zákazníka způsobem zde předpokládaným,
a odškodní Poskytovatele za nároky třetích osob vyplývající z Obsahu
Zákazníka nebo z nasazení Služby Zákazníkem v rozporu s články 2.4 nebo 3.1.

## 8. Trvání, změny a ukončení

8.1 Tato Smlouva platí po dobu, po kterou Službu užíváte.

8.2 Poskytovatel může tuto Smlouvu změnit. Podstatné změny budou Zákazníkům
oznámeny nejméně 30 dní předem a Koncovým uživatelům zveřejněny v Klientovi.
Další užívání po dni účinnosti znamená přijetí změn. Zákazník, který
podstatnou změnu nepřijme, může před tímto dnem Smlouvu bez sankce ukončit.

8.3 Po ukončení Poskytovatel vymaže nebo vrátí Obsah Zákazníka a vymaže
záznamy o Sezení do 30 dnů, s výjimkou případů, kdy je uchování vyžadováno
právními předpisy.

## 9. Rozhodné právo, soudní příslušnost a řešení sporů

9.1 Tato Smlouva se řídí právem České republiky, s vylučením jeho kolizních
norem a Úmluvy OSN o smlouvách o mezinárodní koupi zboží.

9.2 Pro Zákazníky jsou výlučně příslušné soudy v Praze, Česká republika.

9.3 **Spotřebitelé.** Články 9.1 a 9.2 nezbavují Koncového uživatele
vystupujícího jako spotřebitel ochrany podle kogentních norem práva země jeho
obvyklého bydliště ani práva podat žalobu v této zemi podle nařízení (EU)
1215/2012 a nařízení (ES) 593/2008. Spotřebitel v České republice může spor
rovněž řešit mimosoudně u České obchodní inspekce (Štěpánská 15, 120 00
Praha 2, adr.coi.cz); každý spotřebitel v EU může využít síť Evropských
spotřebitelských center.

9.4 Bude-li některé ustanovení shledáno neplatným, zůstávají ostatní
ustanovení v platnosti a neplatné ustanovení se nahradí platným ustanovením
s nejbližším obdobným účinkem.

9.5 **Jazyková znění.** Tato Smlouva existuje v českém a anglickém znění. Pro
spotřebitele s obvyklým bydlištěm v České republice a pro Zákazníky se sídlem
v České republice je rozhodné české znění. V ostatních případech je rozhodné
anglické znění. Toto ustanovení nezbavuje spotřebitele ochrany podle článku
9.3.

---

# Část B — Ustanovení pro Zákazníka (Administrátorská konzole)

## 10. Licence k užívání Služby

10.1 S výhradou této Smlouvy a zaplacení sjednané odměny uděluje Poskytovatel
Zákazníkovi nevýhradní, nepřenosné právo bez možnosti poskytovat podlicence,
a to na dobu trvání Smlouvy, přistupovat k Administrátorské konzoli a umožnit
Koncovým uživatelům užívat Klienta pro vnitřní podnikatelské účely Zákazníka.

10.2 Zákazník nesmí Službu bez předchozí písemné dohody dále prodávat,
pronajímat ani poskytovat třetím osobám formou servisní organizace.

## 11. Administrátorské účty a bezpečnost

11.1 Identity administrátorů jsou spravovány prostřednictvím Keycloaku.
Zákazník odpovídá za zachování důvěrnosti přihlašovacích údajů, za zapnutí
vícefaktorové autentizace, je-li nabízena, za včasné odebrání přístupu
odcházejícím pracovníkům a za veškerou činnost prováděnou pod jeho
administrátorskými účty.

11.2 Zákazník bez zbytečného odkladu uvědomí Poskytovatele o každém podezření
na kompromitaci administrátorského účtu. Poskytovatel uvědomí Zákazníka
o porušení zabezpečení osobních údajů týkajícím se dat Zákazníka bez
zbytečného odkladu a v každém případě tak, aby Zákazník mohl dodržet svou
72hodinovou povinnost podle článku 33 GDPR.

## 12. Obsah Zákazníka a jeho vkládání

12.1 Obsah vkládá Poskytovatel podle pokynů Zákazníka. Zákazník odpovídá za
zákonnost, správnost a aktuálnost Obsahu Zákazníka a za to, že neobsahuje
materiál, k jehož sdílení není oprávněn.

12.2 Zákazník bere na vědomí, že Výstupy jsou odvozeny z Obsahu Zákazníka
a že nesprávný nebo neaktuální vložený obsah povede k nesprávným Výstupům.

12.3 Zákazník bude funkce sledování provozu a Sezení užívat pouze pro
legitimní účely kvality, bezpečnosti a kapacitního plánování, a **nikoli**
ke sledování nebo profilování identifikovatelných osob ani k pokusům
o opětovnou identifikaci Koncových uživatelů ze záznamů o Sezení.

12.4 **Limit uložení.** Administrátorská konzole umožňuje administrátorovi
Zákazníka nastavit maximální objem uchovávaných dat o Sezeních. Tento limit
**nesmí přesáhnout 100 MB** a nelze jej nad tuto hranici nastavit;
administrátor může nastavit kteroukoli nižší hodnotu. Po dosažení nastaveného
limitu jsou mazány nejstarší záznamy o Sezení jako první. Tento mechanismus
působí vedle doby uchování uvedené v dokumentu `PRIVACY-NOTICE-cz.md`
a nezávisle na ní: záznamy jsou mazány podle toho, která skutečnost nastane
dříve. Zákazník bere na vědomí, že nižší limit znamená dřívější zahození
historie Sezení a odpovídající ztrátu údajů pro sledování.

12.5 **Žádné IP adresy.** Služba nezaznamenává IP adresy Koncových uživatelů
a Zákazník nemůže takové zaznamenávání prostřednictvím Administrátorské
konzole zapnout.

## 13. Odměna

`[Odměna, fakturační období, platební podmínky, úrok z prodlení a indexace
budou doplněny, nebo nahrazeny odkazem na objednávkový formulář.]`

---

# Část C — Ustanovení pro Koncového uživatele (anonymní Klient)

## 14. Užívání Klienta

14.1 Klienta můžete užívat k pokládání dotazů k tématu, které provozovatel
zpřístupnil. Není vyžadován žádný účet ani přihlášení a nežádáme vás o jméno
ani kontaktní údaje.

14.2 **Do pole pro dotaz prosím nevkládejte osobní údaje ani důvěrné
informace** — ani své vlastní, ani údaje jiných osob. Dotazy jsou uchovávány
na Serveru společně s časovým údajem, jak je popsáno níže.

14.3 Vašemu sezení je přidělen **náhodný identifikátor**, aby bylo možné
navazující dotazy chápat v kontextu. Není odvozen od vaší identity a **při
každém novém sezení se vytváří úplně nový identifikátor** — nijak vás nemůžeme
rozpoznat jako vracejícího se uživatele ani spojit dnešní dotazy s tím, na co
jste se ptali dříve. Vaše dotazy, Výstupy a časové údaje jsou uchovávány a jsou
dostupné provozovateli daného nasazení, souhrnně i jednotlivě, pro sledování
provozu a kvality.

14.4 Odpovědi generuje systém umělé inteligence a mohou být nesprávné. Služba
odpovídá pouze v rámci nastaveného tématu a u dotazu mimo toto téma uvede, že
odpověď nezná. Vše podstatné si ověřte u oficiálního zdroje a pro závazné
vyjádření kontaktujte přímo provozovatele.

14.5 **Na žádost nemůžeme vaše údaje vymazat a měli byste to vědět, ještě než
cokoli napíšete.** Identifikátor vašeho sezení se zahodí a příště vygeneruje
nový, takže po skončení sezení není v našich záznamech nic, co by vedlo k vám.
Nemůžeme „vaše“ dotazy najít, abychom vám je zobrazili, opravili nebo vymazali
— ani když o to požádáte, ani když vám chceme pomoci. Právě proto je důležitý
článek 14.2: **nevkládejte nic, co byste později chtěli odstranit.** Všechny
záznamy o sezeních se automaticky mažou po uplynutí doby uchování. Článek 11
odst. 2 GDPR nám v takové situaci umožňuje žádosti podle článků 15 až 20
odmítnout a nebudeme vás žádat o identifikační údaje pouze proto, aby taková
žádost byla vůbec proveditelná. Podrobné vysvětlení najdete v dokumentu
`PRIVACY-NOTICE-cz.md`.

14.6 Jste-li spotřebitel, nemají tyto podmínky vliv na vaše kogentní zákonná
práva.

---

## 15. Kontakt

Poskytovatel: České vysoké učení technické v Praze, Český institut informatiky,
robotiky a kybernetiky (CIIRC ČVUT)  
Adresa: Jugoslávských partyzánů 1580/3, 160 00 Praha 6, Česká republika  
E-mail: secretariat@ciirc.cvut.cz  
Ochrana osobních údajů / DPO: dpo@cvut.cz

Repozitář: https://github.com/AlquistAI/insight
