# Alquist Insight — Informace o zpracování osobních údajů

**Verze 1.0 — účinná od 1. října 2026**

Informace podle článků 13 a 14 nařízení (EU) 2016/679 (GDPR).

> **Jazykové znění.** Pro subjekty údajů v České republice je rozhodné toto
> české znění; anglické znění je uvedeno v `PRIVACY-NOTICE.md`.

---

## 1. Kdo je odpovědný

| Role                                                                                 | Subjekt                                                                                                                                |
|--------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| **Správce** Obsahu Zákazníka a dotazů koncových uživatelů                            | organizace provozující konkrétní nasazení (dále jen **Zákazník**) — je uvedena v Klientovi                                             |
| **Zpracovatel** jednající podle pokynů Zákazníka                                     | České vysoké učení technické v Praze – CIIRC, Jugoslávských partyzánů 1580/3, 160 00 Praha 6, IČO 68407700 (dále jen **Poskytovatel**) |
| **Správce** provozních záznamů, bezpečnostního monitoringu a administrátorských účtů | Poskytovatel                                                                                                                           |

Kontakt pro ochranu osobních údajů: dpo@cvut.cz
Dozorový úřad: Úřad pro ochranu osobních údajů, Pplk. Sochora 27,
170 00 Praha 7, Česká republika — uoou.gov.cz. Stížnost můžete podat také
u dozorového úřadu ve svém členském státě EU.

## 2. Co zpracováváme

**Klient (anonymní rozhraní pro dotazy)**

| Údaj                                                                                   | Účel                                                                     | Právní základ                                                                                            |
|----------------------------------------------------------------------------------------|--------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Náhodný identifikátor sezení, generovaný nově pro každé sezení a opakovaně nepoužívaný | udržení kontextu konverzace u navazujících dotazů v rámci jednoho sezení | čl. 6 odst. 1 písm. f) — oprávněný zájem na funkční službě / čl. 6 odst. 1 písm. b), existuje-li smlouva |
| Text dotazu a vygenerovaná odpověď                                                     | vytvoření odpovědi; sledování kvality a provozu provozovatelem           | čl. 6 odst. 1 písm. f) — oprávněný zájem provozovatele                                                   |
| Časový údaj u každé zprávy                                                             | sledování provozu, kapacitní plánování, odhalování zneužití              | čl. 6 odst. 1 písm. f)                                                                                   |
| Provozní a chybové záznamy, bez IP adres                                               | bezpečnost, řešení potíží                                                | čl. 6 odst. 1 písm. f)                                                                                   |

**IP adresy nezaznamenáváme.** Klient neukládá společně s vašimi dotazy žádný
síťový identifikátor a do záznamů o sezeních ani do aplikačních logů se
nezapisuje žádná IP adresa. Jde o záměrné rozhodnutí: IP adresa by byla trvalým
identifikátorem umožňujícím spojit vaše jednotlivá sezení, což by zmařilo
ochranu popsanou v části 2.1.

**Nežádáme** vás o jméno, e-mailovou adresu ani o žádný účet. Nevytváříme
reklamní profily, údaje neprodáváme a nedochází k žádnému automatizovanému
rozhodování podle článku 22 GDPR s právními účinky pro vás.

### 2.1 Identifikátor sezení a proč vás nemůžeme najít

Identifikátor sezení je náhodná hodnota bez jakékoli souvislosti s vaší
identitou a **při každém zahájení sezení se generuje nový**. Není trvale
uchováván, není opakovaně používán a nikdy není spojen s předchozím ani
následujícím sezením.

Praktické důsledky jsou tyto:

- Nemůžeme vás rozpoznat jako vracejícího se uživatele.
- Nemůžeme sestavit historii ani profil jedné osoby přes více návštěv. Jediné
  seskupení, které dokážeme provést, je seskupení dotazů **v rámci jednoho
  sezení**, dokud je aplikace otevřena v prohlížeči.
- Po skončení vašeho sezení **neexistuje v našich systémech nikde žádný
  identifikátor, který by vedl k vám.** Záznamy se stávají samostatnou
  posloupností dotazů, odpovědí a časových údajů, odtrženou od jakékoli
  možnosti přiřazení.
- Nezaznamenáváme vaši IP adresu (viz poznámka u tabulky výše), takže
  neexistuje žádný identifikátor na síťové úrovni, kterým by bylo možné
  záznamy znovu spojit s vámi nebo propojit jedno sezení s druhým.

Přesto nadále považujeme záznamy o sezeních za **osobní údaje**, nikoli za
anonymní údaje, a uplatňujeme na ně plné záruky podle GDPR, protože text dotazu
může sám o sobě prozradit, kdo jej napsal (například pokud v něm uvedete své
jméno, adresu nebo své okolnosti). Tuto opatrnější klasifikaci jsme zvolili
záměrně. Její limity jsou poctivě popsány v části 5.

**Cookies / místní úložiště.** Identifikátor sezení existuje pouze v paměti
stránky / v sessionStorage po dobu trvání sezení a při jeho ukončení je
zahozen. Nepoužívá se pro něj žádná trvalá cookie ani záznam v localStorage.
V rozsahu, v jakém je úložiště prohlížeče využito, je nezbytně nutné pro
službu, kterou jste si vyžádali, a je proto vyňato z povinnosti souhlasu podle
§ 89 odst. 3 zákona č. 127/2005 Sb. a článku 5 odst. 3 směrnice 2002/58/ES.
Bude-li přidána analytika nebo jiné nikoli nezbytné úložiště, je nutné
předem získat souhlas.

**Administrátorská konzole**

| Údaj                                                           | Účel                                             | Právní základ               |
|----------------------------------------------------------------|--------------------------------------------------|-----------------------------|
| Jméno administrátora, e-mail, role, identifikátory v Keycloaku | autentizace, řízení přístupu, odpovědnost        | čl. 6 odst. 1 písm. b) a f) |
| Auditní záznam administrátorských úkonů                        | bezpečnost, dohledatelnost změn vloženého obsahu | čl. 6 odst. 1 písm. c) a f) |

**Obsah Zákazníka.** Vložené dokumenty mohou obsahovat osobní údaje. O tom, co
je vloženo, rozhoduje Zákazník, který je pro tyto údaje správcem. Zákazníci jsou
instruováni, aby nevkládali zvláštní kategorie údajů (čl. 9 GDPR) bez
zdokumentovaného právního základu a předchozího posouzení.

## 3. Kde se údaje zpracovávají a komu se předávají

| Příjemce                            | Role                                               | Umístění                      | Záruka                                                                                                                    |
|-------------------------------------|----------------------------------------------------|-------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Hetzner Online GmbH                 | hostování Serveru                                  | Německo / Finsko — EU         | EU/EHP, nedochází k předání                                                                                               |
| OpenAI Ireland Ltd / OpenAI, L.L.C. | generování odpovědí z dotazu a vyhledaných výňatků | EU, je-li dostupná; jinak USA | dodatek o zpracování údajů s standardními smluvními klauzulemi EU (rozhodnutí 2021/914) / rámcem EU–USA pro ochranu údajů |
| Keycloak                            | autentizace administrátorů                         | hostováno na Serveru          | samostatné předání nedochází                                                                                              |

**Předávání mimo EHP.** Pokud odpovědi generuje endpoint OpenAI mimo EHP,
opírá se předání o výše uvedenou záruku doplněnou posouzením dopadů předání.
Podle podmínek API sjednaných Poskytovatelem **nejsou předaná data užívána
k trénování modelů OpenAI**. Kopii záruk poskytneme na žádost zaslanou na
kontakt uvedený v části 1.

Údaje mohou být rovněž zpřístupněny orgánům veřejné moci, je-li k tomu
Poskytovatel právně povinen, a odborným poradcům vázaným povinností
mlčenlivosti.

## 4. Jak dlouho údaje uchováváme

| Údaj                                                                      | Doba uchování                                                                                                                                                                                                                                           |
|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Záznamy o sezeních (dotazy, odpovědi, časové údaje, identifikátor sezení) | 90 dnů, poté vymazány nebo nevratně agregovány do statistik. Mazání je **založeno na věku záznamu a uplatňuje se na všechny záznamy stejně**; protože neexistuje trvalý identifikátor, nelze jednotlivé záznamy vybrat k dřívějšímu výmazu (viz část 5) |
| Provozní záznamy (bez IP adres)                                           | 30 dnů                                                                                                                                                                                                                                                  |
| Administrátorské účty                                                     | po dobu trvání účtu a dalších 6 měsíců                                                                                                                                                                                                                  |
| Administrátorské auditní záznamy                                          | 12 měsíců                                                                                                                                                                                                                                               |
| Obsah Zákazníka                                                           | po dobu trvání smlouvy, výmaz do 30 dnů od ukončení                                                                                                                                                                                                     |
| Záložní kopie                                                             | 30 dnů, rotující                                                                                                                                                                                                                                        |

Doby uchování stanoví Zákazník jako správce; výše uvedené hodnoty jsou výchozí
nastavení Poskytovatele a lze je písemným pokynem zkrátit nebo prodloužit.

### 4.1 Objemový limit uložení

Vedle časového limitu uvedeného výše nastavuje administrátor **maximální objem
uchovávaných dat o sezeních**. Tento limit **nesmí přesáhnout 100 MB** a nad
tuto hranici jej nelze zvýšit; administrátor může nastavit kteroukoli nižší
hodnotu. Jakmile uchovávaná data dosáhnou nastaveného limitu, jsou **nejstarší
záznamy mazány jako první**, aby byl limit dodržen.

Limit tedy funguje jako druhý, nezávislý mechanismus mazání: záznamy jsou
odstraněny buď po uplynutí doby uchování, **nebo** při dosažení objemového
limitu, podle toho, co nastane dříve. Stanoví tvrdou horní hranici objemu
textu dotazů, který může v daném okamžiku na Serveru existovat.

Limit je nástrojem kontroly objemu, nikoli náhradou časového limitu — při
nízkém provozu může záznam zůstat až do uplynutí doby uchování. Oba mechanismy
se uplatňují společně.

## 5. Vaše práva

Máte právo požadovat **přístup** (čl. 15), **opravu** (čl. 16), **výmaz**
(čl. 17), **omezení zpracování** (čl. 18), **přenositelnost údajů** (čl. 20)
a **vznést námitku** proti zpracování založenému na oprávněném zájmu (čl. 21).
Máte právo podat stížnost u dozorového úřadu (čl. 77). Uplatnění těchto práv je
bezplatné a odpovíme do jednoho měsíce.

### Důležité omezení pro anonymní uživatele Klienta — přečtěte si prosím

**Na žádost nemůžeme vaše dotazy vymazat a chceme to říci přímo, místo abychom
naznačovali něco jiného.**

Protože se identifikátor sezení generuje pro každé sezení znovu a není
uchováván, nedržíme nic, co by spojovalo kterýkoli uchovaný dotaz s konkrétní
osobou. Když nás požádáte o výmaz, opravu, zobrazení nebo export „svých“ údajů,
nemáme žádný prostředek, jak určit, které záznamy jsou vaše. Neexistuje žádné
vyhledání, které bychom mohli provést, žádný účet, s nímž bychom mohli údaje
spárovat, ani žádný identifikátor, který by vaše sezení přežil. Nepomůže ani
to, když nás o identifikátor požádáte dodatečně, protože na naší straně již
jako klíč k těmto záznamům neexistuje.

Ve vztahu k záznamům o sezeních v Klientovi to znamená:

- **Výmaz (čl. 17)** — nemůžeme provést cílený výmaz. Všechny záznamy
  o sezeních se namísto toho mažou automaticky po uplynutí doby uchování podle
  části 4, nebo dříve při dosažení objemového limitu podle části 4.1, bez
  potřeby jakékoli žádosti.
- **Přístup (čl. 15) a přenositelnost (čl. 20)** — nemůžeme vaše záznamy
  vyhledat a poskytnout vám jejich kopii.
- **Oprava (čl. 16) a omezení zpracování (čl. 18)** — nemůžeme vaše záznamy
  vyčlenit, abychom je změnili nebo omezili.
- **Námitka (čl. 21)** — zpracování můžete kdykoli ukončit jednoduše tím, že
  aplikaci zavřete; žádné další údaje o vás nebudou shromažďovány. K námitce
  rovněž přihlédneme do budoucna.

Právě tuto situaci řeší článek 11 GDPR. Není-li správce schopen identifikovat
subjekt údajů, stanoví článek 11 odst. 2, že články 15 až 20 se nepoužijí,
neposkytne-li subjekt údajů dodatečné informace umožňující jeho identifikaci.
Žádné takové informace nedržíme a **nebudeme vás žádat o poskytnutí
identifikačních údajů pouze proto, aby bylo možné žádost zpracovat** —
shromažďovat o vás více údajů kvůli vyřízení žádosti týkající se ochrany
soukromí by popíralo samotný účel tohoto návrhu. Pokud dokážete prokázat, které
záznamy jsou vaše, vaší žádosti vyhovíme.

Považujeme to za přijatelný kompromis, protože tatáž architektura, která nám
brání vaše údaje najít, brání i komukoli jinému — včetně provozovatele, našich
zaměstnanců a případného budoucího nabyvatele služby — vytvořit si o vás
profil. **Ochrana vyplývá z toho, že údaje nedržíme, nikoli ze slibu, že s nimi
budeme dobře zacházet.** Odpovídající cenou je ztráta možnosti cíleného výmazu
a praktickým opatřením je článek 14.2 licenční smlouvy: nevkládejte do pole pro
dotaz nic, co byste později chtěli odstranit.

Vaše právo podat stížnost u dozorového úřadu podle článku 77 tím není dotčeno,
stejně jako vaše právo na soudní ochranu.

**U administrátorských účtů a Obsahu Zákazníka je situace jiná.** Tyto záznamy
jsou identifikovatelné a všechna výše uvedená práva lze uplatnit v plném
rozsahu — u administrátorů prostřednictvím Poskytovatele a u osobních údajů
obsažených ve vloženém obsahu prostřednictvím Zákazníka jako správce.

U údajů z Klienta a Obsahu Zákazníka o žádostech rozhoduje **Zákazník** jako
správce. Svou žádost zašlete buď provozovateli uvedenému v Klientovi, nebo na
kontakt Poskytovatele uvedený výše; Poskytovatel ji předá dál.

## 6. Bezpečnost

Opatření zahrnují šifrování při přenosu (TLS), šifrování při uložení kde je
to relevantní, řízení přístupu podle rolí prostřednictvím Keycloaku,
vícefaktorovou autentizaci administrátorů je-li zapnuta, síťovou izolaci
Serveru, přístup pracovníků Poskytovatele vázaných mlčenlivostí podle zásady
minimálních oprávnění, zaznamenávání administrátorských úkonů a pravidelné
aktualizace a záložní kopie. `[Odkaz na úplnou přílohu technických
a organizačních opatření ve smlouvě o zpracování osobních údajů.]`

## 7. Automatizované generování obsahu

Odpovědi vytváří velký jazykový model a mohou být nepřesné. Na základě tohoto
zpracování o vás není přijímáno žádné rozhodnutí. Podle článku 50 nařízení (EU)
2024/1689 (akt o AI) jste informováni, že komunikujete se systémem umělé
inteligence; Klient toto oznámení zobrazuje.

## 8. Změny

Podstatné změny těchto informací budou zveřejněny v Klientovi a oznámeny
Zákazníkům nejméně 30 dní předem. Verze a datum účinnosti jsou uvedeny
v záhlaví.
