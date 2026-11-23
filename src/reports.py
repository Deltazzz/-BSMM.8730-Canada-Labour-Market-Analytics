"""Typeset the final and retrospective midterm reports from validated release tables."""
import csv
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from pipeline import ROOT, RESULTS, CATALOGUE

OUT = ROOT/"reports"
OUT.mkdir(exist_ok=True)
TEAL, INK, SOFT, LINE = [colors.HexColor(s) for s in ("#0E6062","#172E36","#425B61","#CBD8D6")]
MONTHS = ["2026-08","2026-09","2026-10"]
SHORT = ["Aug","Sept","Oct"]
SURVEY = "https://www150.statcan.gc.ca/n1/pub/75-514-g/75-514-g2023001-eng.htm"

def read(name):
    with (RESULTS/(name+".csv")).open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def integer(v):
    return f"{int(v):,}"

def money(v):
    from decimal import Decimal, ROUND_HALF_UP
    return "$"+format(Decimal(str(v)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP),",.2f")

def share(a,b):
    return f"{100*int(a)/int(b):.1f}%"

def style(f="Helvetica",size=11,lead=15,col=INK,align=TA_LEFT):
    return ParagraphStyle("body",fontName=f,fontSize=size,leading=lead,textColor=col,alignment=align)

class Report:
    def __init__(self, name, kind):
        self.out = Canvas(str(OUT/name),pagesize=letter,invariant=True)
        self.out.setTitle(kind+" | Canadian Job Bank, August to October 2026")
        self.out.setAuthor("BSMM.8730 project")
        self.kind=kind
        self.page=0

    def begin(self,section,title):
        if self.page:
            self.finish_page()
        self.page+=1
        c=self.out
        c.setFont("Helvetica-Bold",9)
        c.setFillColor(TEAL)
        c.drawString(46,751,"BSMM.8730  /  DATA ACQUISITION AND MANAGEMENT")
        c.setFont("Helvetica",9)
        c.drawRightString(566,751,self.kind.upper())
        self.y=719
        self.text(escape(section),style("Helvetica-Bold",10,13,TEAL),5)
        self.text(escape(title),style("Times-Bold",25,28),13)

    def text(self,t,st=None,gap=8):
        p=Paragraph(t,st or style())
        _,h=p.wrap(520,700)
        self.y-=h
        p.drawOn(self.out,46,self.y)
        self.y-=gap

    def h(self,t):
        self.y-=3
        self.text(t,style("Helvetica-Bold",14,17,TEAL),6)

    def table(self, headers, data, widths, left=1):
        if sum(widths)!=520:
            raise ValueError("Table width")
        for i,row in enumerate([headers]+list(data)):
            boxes=[]
            for j,(v,w) in enumerate(zip(row,widths)):
                f="Helvetica-Bold" if i==0 else "Helvetica"
                st=style(f,9.1,11.5,colors.white if i==0 else INK, TA_LEFT if j<left else TA_RIGHT)
                p=Paragraph(escape(str(v)),st)
                boxes.append((p,p.wrap(w-13,500)[1],w))
            height=max(x[1] for x in boxes)+10
            if i==0 or i%2==0:
                self.out.setFillColor(TEAL if i==0 else colors.HexColor("#F0F5F3"))
                self.out.rect(46,self.y-height,520,height,fill=1,stroke=0)
            x=46
            for p,h,w in boxes:
                p.drawOn(self.out,x+6,self.y-(height+h)/2)
                x+=w
            self.y-=height
        self.y-=10

    def note(self,t):
        self.text(t,style("Helvetica-Oblique",9,12,SOFT),7)

    def finish_page(self):
        if self.y<42:
            raise OverflowError(f"{self.kind} page {self.page}: content ends at {self.y:.1f}")
        c=self.out
        c.setStrokeColor(LINE)
        c.line(46,37,566,37)
        c.setFillColor(SOFT)
        c.setFont("Helvetica",8.5)
        c.drawString(46,23,"Government of Canada Job Bank  |  English monthly releases, August to October 2026")
        c.drawRightString(566,23,str(self.page))
        c.showPage()

    def save(self):
        self.finish_page()
        self.out.save()

def link(url,label):
    return f'<link href="{url}" color="#0E6062"><u>{escape(label)}</u></link>'

def build():
    monthly=read("monthly")
    occ=read("occupations")
    provinces=read("provinces")
    geography=read("geography")
    quality=read("consistency")
    pay=read("pay")
    coverage=read("coverage")
    quals=read("qualifications")
    by_occ={(r["posting_month"],r["noc"]):r for r in occ}
    r=Report("D5 Final report.pdf","D5 Final report")
    r.begin("August to October 2026","What changed in Canadian Job Bank postings?")
    r.text("Job Bank recorded 59,130 newly listed posting-location records in October, up 5,331 (9.9%) from August. External feeds added 6,018 records while direct postings fell by 687. The rise therefore reflects how listings reached Job Bank as well as what employers advertised.",style("Times-Roman",15.4,19.5),13)
    r.h("Three months of first-posting dates")
    r.table(["Measure","August","September","October"],[
        [label]+[integer(a[k]) for a in monthly] for label,k in [
        ("Posting-location records","records"),("Openings on those records","advertised_openings"),
        ("Advertised directly","direct"),("From external feeds","external")]]+
        [["External share"]+[share(a["external"],a["records"]) for a in monthly],
         ["Records per calendar day"]+[f"{float(a['records_per_day']):,.1f}" for a in monthly]], [214,102,102,102])
    r.text("September had fewer records than August and one fewer calendar day. Its average rose slightly, from 1,735.5 to 1,745.6 per day. October rose on both measures. No seasonal adjustment was applied.")
    r.h("What the records count")
    r.text("Each row carries a WIC Job Location Snapshot ID, a first posting date and a vacancy count. Across the releases, all 165,297 IDs were distinct. A position advertised for several locations can generate several records, and a single record can offer many openings. The files contain no stable requisition or employer key that would identify every repost.")
    r.text("For students and career planners, the figures describe opportunities advertised through Job Bank and its contributors. National employment, hiring, vacancy rates and realized earnings require different evidence.")
    r.note("Source for all calculations: "+link(CATALOGUE,"Employment and Social Development Canada, Job Bank monthly open data")+". Coverage, transformations and sources appear on page 6.")

    r.begin("Occupations and geography","Retail listings and harvesting openings rose")
    r.table(["NOC 2021 occupation","Aug records","Sept records","Oct records","Oct openings"],[
        [label]+[integer(by_occ[(m,n)]["records"]) for m in MONTHS]+[integer(by_occ[(MONTHS[-1],n)]["advertised_openings"])]
        for n,label in [("64100","Retail salespersons and visual merchandisers"),("63200","Cooks"),("85101","Harvesting labourers"),("85100","Livestock labourers"),("73300","Transport truck drivers")]], [207,75,75,75,88])
    r.text("A narrow group explains the retail swing. From October 9 to 15, 3,745 external retail records listed exactly $111,360 per year, with four original titles across 724 distinct city labels and all 13 provinces and territories. No record met this definition in August or September. Leaving it out as a sensitivity check gives 1,657 October retail records, below August’s 1,810. Across all occupations, the August-to-October increase falls from 9.9% to 2.9%.")
    r.text("Harvesting labourers averaged 12.8 openings per October record. They accounted for 28,036 of October’s 126,074 advertised openings (22.2%). Counting records alone understates the weight of multi-opening advertisements for this occupation.")
    r.h("The largest province and the largest change differed")
    prov={(v["posting_month"],v["province"]):v for v in provinces}
    reg={(v["posting_month"],v["economic_region"]):v for v in geography}
    r.table(["Listed location","August","September","October"],[[label]+[integer(d[(m,k)]["records"]) for m in MONTHS] for d,k,label in [
        (prov,"Ontario","Ontario"),(prov,"Québec","Québec"),(prov,"British Columbia","British Columbia"),
        (reg,"Toronto Region","Toronto economic region, ON"),(reg,"Lower Mainland–Southwest Region","Lower Mainland–Southwest, BC")]], [226,98,98,98])
    r.text("Ontario led each month. Québec added 4,196 records between August and October. Toronto and Lower Mainland–Southwest are parts of their respective provinces. Adding the region and province rows would count some records twice.")
    r.note("Region was unavailable on 393 August, 322 September and 1,067 October records. Province counts cover all 13 jurisdictions. Full geographic and occupational breakdowns are in the accompanying results.")

    r.begin("Education and experience","Qualification evidence comes from direct postings")
    r.text("Education and experience were populated on every direct record and absent from every external record. Direct records accounted for 42.4% of August, 42.5% of September and 37.4% of October. A change in the mix of sources can change the apparent prevalence of a requirement even when employers’ stated requirements remain similar.")
    r.table(["Scope","August","September","October"],[
        ["Records with both requirements"]+[integer(x["known_education"]) for x in monthly],
        ["Records missing both requirements"]+[integer(x["external"]) for x in monthly],
        ["Cooks with known requirements"]+[integer(by_occ[(m,"63200")]["direct"]) for m in MONTHS],
        ["Truck drivers with known requirements"]+[integer(by_occ[(m,"73300")]["direct"]) for m in MONTHS]], [238,94,94,94])
    r.h("Requirements in two occupations")
    qcells=[("Education","Secondary (high) school graduation certificate","High school certificate"),
            ("Education","No degree, certificate or diploma","No formal credential"),
            ("Experience","1 year to less than 2 years","1 to under 2 years of experience"),
            ("Experience","No experience","No experience required")]
    qrows=[]
    for dim,level,label in qcells:
        line=[label]
        for n in ["63200","73300"]:
            total=sum(int(by_occ[(m,n)]["direct"]) for m in MONTHS)
            num=sum(int(x["records"]) for x in quals if x["noc"]==n and x["dimension"]==dim and x["level"]==level)
            line.append(f"{num:,} ({share(num,total)})")
        qrows.append(line)
    r.table(["Stated requirement","Cooks (n = 3,862)","Truck drivers (n = 2,243)"],qrows,[220,145,155])
    r.text("Among records with a known requirement, 42.8% of cooks’ listings asked for one to under two years of experience. In truck driving, 47.7% explicitly accepted no experience. Requirements can include other conditions, such as a licence, beyond these structured education and experience fields.")
    r.text("For cooks, the share of direct records asking for one to under two years was 43.5%, 42.5% and 42.3% in month order. A prospective applicant can use this comparison when choosing which listings to read in full.")
    r.note("Each percentage uses the records in the named occupation with a known field. Rows show selected categories from two separate questions. Full distributions by month and NOC are in qualifications.csv.")

    r.begin("Advertised compensation","Hourly and annual offers moved differently")
    r.text("For each valid record, the midpoint is the average of its lower and upper advertised amounts. The figures below are unweighted medians across posting-location records. Each pay period is analysed separately. Fixed offers enter with equal bounds.")
    paymap={(x["posting_month"],x["scope"],x["noc"],x["province"],x["salary_per"]):x for x in pay}
    hourly=[paymap[(m,"Canada","","","Hour")] for m in MONTHS]
    annual=[paymap[(m,"Canada","","","Year")] for m in MONTHS]
    r.table(["Eligible ranges and medians","August","September","October"],[
        ["Hourly records"]+[integer(a["comparable_records"]) for a in hourly],
        ["Median hourly lower bound"]+[money(a["median_lower"]) for a in hourly],
        ["Median hourly upper bound"]+[money(a["median_upper"]) for a in hourly],
        ["Median hourly midpoint"]+[money(a["median_midpoint"]) for a in hourly],
        ["Annual records"]+[integer(a["comparable_records"]) for a in annual],
        ["Median annual midpoint"]+["$"+integer(float(a["median_midpoint"])) for a in annual]], [211,103,103,103])
    r.text("The October annual midpoint median was $96,500. Excluding the repeated retail group described on page 2 lowered it to $77,500 across 7,563 annual records. A change in the composition of adverts can move the median substantially.")
    r.h("October hourly offers within occupation and province")
    payrows=[]
    for n,label in [("63200","Cooks"),("73300","Truck drivers")]:
        for pr in ["Alberta","British Columbia","Ontario"]:
            a=paymap[("2026-10","Occupation and province",n,pr,"Hour")]
            payrows.append([label,pr,integer(a["comparable_records"]),money(a["median_lower"]),money(a["median_upper"]),money(a["median_midpoint"])])
    r.table(["Occupation","Province","Records","Lower¹","Upper¹","Midpoint¹"],payrows,[95,127,71,72,72,83],2)
    r.note("¹ Separate medians of each measure, in advertised dollars per hour. These are nominal offers. Differences can reflect changing mixes of employers, locations and job duties.")
    r.text("A sensitivity screen excluded hourly ranges below $5 at the lower end or above $500 at the upper end. The monthly midpoint medians became $24.00, $23.72 and $23.50. Both endpoint medians were unchanged. The screen is a diagnostic choice, not a wage-floor assumption.")

    r.begin("Employment and work arrangements","Full-time work was common among known records")
    r.table(["Measure","August","September","October"],[
        ["Full-time / known type"]+[share(x["full_time"],x["known_type"]) for x in monthly],
        ["Known employment type"]+[integer(x["known_type"]) for x in monthly],
        ["Permanent / known duration"]+[share(x["permanent"],x["known_term"]) for x in monthly],
        ["Known duration"]+[integer(x["known_term"]) for x in monthly],
        ["Weekend work / known flag"]+[share(x["weekend_yes"],x["weekend_known"]) for x in quality],
        ["Evening work / known flag"]+[share(x["evening_yes"],x["evening_known"]) for x in quality],
        ["Known weekend and evening flags"]+[integer(x["weekend_known"]) for x in quality]], [220,100,100,100])
    r.text("Valid weekly hours ranges appeared on 21,732, 21,347 and 21,142 records. The median minimum was 35 hours per week and the median maximum was 40 in every month. Listings with another hours period or with no specified period are outside these summaries.")
    r.h("A remote-work prevalence estimate is unavailable")
    r.text("All 67,173 direct records carried an explicit No in the telework field. All 98,124 external records left it empty. Within the repeated October retail group alone, 931 original titles contained “WFH”. This establishes that remote-work language appeared where the flag was unavailable. Counting those titles cannot establish the number of distinct remote jobs.")
    r.h("Benefits and commission need the same care")
    r.text("The dental and commission flags were No wherever they were populated. A separate commission-type field nevertheless contained 182, 172 and 111 values across the three months. The flags do not support a conclusion that benefits or commission were absent. The underlying fields and their monthly coverage are included in the cleaned dataset.")
    r.note("Employment shares use a known response for the specific field. Multiple schedule flags can be selected on the same record. A listing may advertise both evening and weekend work.")

    r.begin("Methods and interpretation","How to reproduce and use the evidence")
    r.h("Source and period")
    r.text("The study starts with the proposal’s August release and extends through the next two consecutive releases. The official August file reproduced the proposal’s 53,799 records and 65 columns. The September and October releases also have 65 fields. English files supply one language version of records from direct Job Bank advertisements and eligible external feeds.")
    r.table(["Release","First date","Last date","Days","Rows","Repeated IDs¹"],[
        [m["release_month"],m["first_date"],m["last_date"],m["distinct_dates"],integer(m["records"]),str(int(m["duplicate_ids_within"])+int(m["ids_in_earlier_releases"]))] for m in coverage],[79,103,103,54,84,97])
    r.note("¹ Repetition within the release or in earlier releases. Each row had a valid positive vacancy count. Source hashes and full download URLs are recorded in sources.csv.")
    r.h("Preparation and checks")
    r.text("Python read the preserved UTF-16 tab-delimited files, checked field widths and types, preserved leading zeros in NOC codes, normalized dates and mapped missing markers to null. Each clean record retains its source release and logical row number. Repeated business descriptions with different snapshot IDs remain separate.")
    r.text("SQL joined releases to records, tabulated known and missing values, and calculated medians within original pay units. Across the three files, 295 records lacked a pay unit or bound and one had a nonpositive bound. They remain in posting counts. September had 1,485 missing NOC codes, versus 354 in August and 439 in October.")
    r.h("What can be inferred")
    r.text("These descriptive comparisons cover three unadjusted months. There are no application, hiring or filled-vacancy outcomes, population weights or complete employer IDs. The increase could reflect seasonal advertising, changes in contributor activity or recruitment across multiple locations. These files cannot separate those explanations.")
    r.text("Use the Power BI occupation drill-through to compare locations, sample sizes and hourly ranges. For a population-level vacancy question, consult Statistics Canada’s survey definitions and reference period before comparing its measures.")
    r.note("Sources: "+link(CATALOGUE,"Government of Canada Job Bank catalogue")+" and "+link(SURVEY,"Statistics Canada, Guide to the Job Vacancy and Wage Survey")+". The README contains rebuild commands. The Python and SQL sources, field dictionary and audit tables accompany this report.")
    r.save()

    r=Report("D3 Midterm report.pdf","D3 Midterm report")
    r.begin("Retrospective milestone summary","Two releases establish a comparable starting point")
    r.text("The August and September 2026 Job Bank files contain 106,167 posting-location records. September had 1,431 fewer records (2.7%) than August. It also had one fewer calendar day. The daily rate rose modestly, so the monthly count alone gives an incomplete picture.")
    r.table(["Validation and initial results","August","September"],[
        ["First-posting date range","Aug 1–31","Sept 1–30"],
        ["Fields / distinct first-posting dates","65 / 31","65 / 30"],
        ["Distinct snapshot IDs","53,799","52,368"],
        ["Advertised openings","96,054","95,555"],
        ["Records per calendar day","1,735.5","1,745.6"],
        ["Direct records with stated education","22,800","22,260"],
        ["Median advertised hourly midpoint","$24.00","$23.83"]],[254,133,133])
    r.h("Acquisition and preparation")
    r.text("Each raw release has a pinned SHA-256 hash and a traceable source URL. The Python pipeline handles tab delimiters and UTF-16 encoding, supports a common 65-field schema, and preserves location IDs and occupational codes. No ID occurred twice within or across these two files. The database stores both original pay bounds and their stated unit.")
    r.h("Initial interpretation and remaining questions")
    r.text("Cook records rose from 2,483 to 2,509. Direct and external contributions both matter, while qualifications were available only on direct records. The final solution adds October, checks whether repeated listings affect the comparison, and examines pay, geography and working conditions by occupation.")
    r.note("Prepared from the archived releases as a retrospective D3 deliverable. It documents a two-month checkpoint and makes no claim about the original submission date. Source: "+link(CATALOGUE,"ESDC Job Bank catalogue")+".")
    r.save()

if __name__=="__main__":
    build()
