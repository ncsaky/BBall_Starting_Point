"""Name lists for made-up staff (coaches, analysts, scouts, medical and development staff).

Names come in regional groups so a first name and a last name read as one plausible person, with a share of
English first names in every group (second-generation Americans, players' families abroad). Unisex first names
(Jordan, Taylor, Jamie, Quinn, Kelly, Morgan...) are left out on purpose: a staff member's name must never read
as the other gender from the face shown next to it. Real NBA head coaches' full names are not reproduced.
"""

from __future__ import annotations

US_MALE = """
Aaron Adam Alan Alonzo Andre Andrew Anthony Barry Ben Blake Bobby Brad Brandon Brent Brett Brian Bruce Bryce
Byron Calvin Cameron Carl Cedric Chad Charles Chris Clarence Cliff Cody Cole Corey Craig Curtis Dale Damon Dan Dante
Darius Darnell Darrell Dave David Dean Demetrius Dennis Derek Derrick Desmond DeShawn Don Doug Dustin Dwayne
Ed Elijah Elliot Eric Evan Frank Gabe Garrett Gary Gene Glenn Grant Greg Hank Harold Ian Isaiah Jack Jake Jalen
Jamal James Jared Jarvis Jason Jay Jeff Jeremy Jerome Joe John Jon Josh Julian Justin Kareem Keith Kendrick Kenny
Kevin Kurt Kyle Lamar Lance Larry Lionel Lonnie Luke Malik Marcus Mark Marlon Marvin Mason Matt Maurice Mike Mitch
Nate Neil Nick Noah Nolan Omar Otis Owen Paul Pete Phil Rashad Rasheed Ray Reggie Reid Rick Rob Roderick Rodney Ron
Ross Russ Ryan Scott Sean Seth Shane Sherman Spencer Stan Steve Ted Terrence Terry Theo Tim Todd Tom Tony Travis
Tremaine Trent Troy Ty Tyler Tyrone Vernon Vince Wade Walt Warren Wes Will Willie Xavier Zach
"""

US_FEMALE = """
Aaliyah Abby Alicia Allison Amanda Amber Amy Andrea Angela Ashley Becca Becky Brianna Brittany Brooke Caitlin Candace
Carly Carrie Cassandra Chelsea Christina Claire Courtney Crystal Danielle Dawn Denise Diana Ebony Elizabeth Emily
Erica Erin Gina Grace Hannah Heather Holly Imani Jada Jasmine Jenna Jennifer Jenny Jessica Jill Julia Julie Kara
Karen Kate Katie Kayla Keisha Kendra Kiara Kim Kristen Kristin Latoya Lauren Lindsay Lisa Lori Madison
Mandy Megan Meghan Melissa Michelle Molly Monica Monique Natalie Natasha Nia Nicole Olivia Paige Rachel Rebecca
Renee Sabrina Sarah Shanice Sharon Simone Stephanie Tamika Tanisha Tara Teresa Tiffany Tracy Vanessa Wendy Whitney
Yvonne
"""

US_LAST = """
Adams Alexander Allen Anderson Andrews Armstrong Arnold Austin Bailey Baker Barnes Beasley Becker Bell Bennett Berry
Bishop Black Boyd Bradley Brennan Brooks Brown Bryant Burns Butler Byrd Calloway Campbell Carpenter Carr Carroll
Carter Chapman Clark Cole Coleman Collins Cook Cooper Cox Crawford Cunningham Daniels Davis Dixon Donovan Duncan
Dunn Dupree Edwards Elliott Ellis Evans Ferguson Fields Fisher Fleming Ford Foster Fox Franklin Friedman Gaines
Gallagher Gardner Gibson Goldberg Gordon Graham Grant Gray Green Greene Griffin Hamilton Harper Harris Harrison
Hart Hawkins Hayes Haywood Henderson Hicks Hill Hoffman Holloway Holmes Howard Hudson Hughes Hunter Jackson James
Jenkins Johnson Jones Katz Kennedy King Kirkland Klein Knight Kowalski Kramer Lane Lawrence Lawson Levine Lewis
Lockhart Long Marshall Martin Mason Matthews McCarthy McCoy McDonald Miller Mills Mitchell Monroe Moore Morgan
Morris Murphy Myers Nelson Novak O'Brien Olson Owens Palmer Parker Patterson Payne Perkins Perry Peterson Phillips
Pierce Porter Powell Price Pruitt Reed Reynolds Rice Richardson Riley Robertson Robinson Rogers Rosen Ross Russell
Ryan Sanders Schmidt Schultz Scott Shapiro Shaw Simmons Sims Smith Snyder Spencer Stephens Stewart Stone Sullivan
Sutton Tate Taylor Thomas Thompson Thornton Tucker Turner Vaughn Wagner Walker Wallace Walsh Ward Warren Washington
Watkins Watson Weaver Weiss Wells West White Whitaker Whitfield Williams Willis Wilson Wood Woods Wright Young
"""

REGIONS: dict[str, dict] = {
    "us": {"weight": 70, "english_first": 1.0, "male": "", "female": "", "last": US_LAST},
    "latin": {
        "weight": 8, "english_first": 0.25,
        "male": "Adrián Alejandro Álvaro Andrés Bruno Carlos Diego Eduardo Fernando Gabriel Héctor Iván Javier Joaquín "
                "Jorge Lucas Luis Manuel Marcelo Mateo Miguel Nicolás Óscar Pablo Rafael Raúl Ricardo Rodrigo Sergio Tiago",
        "female": "Adriana Ana Beatriz Camila Carmen Claudia Daniela Elena Gabriela Isabel Laura Lucía María Mariana Marta "
                  "Natalia Patricia Paula Sofía Valeria",
        "last": "Aguilar Álvarez Cabrera Castillo Castro Costa Delgado Díaz Fernández Flores García Gómez González "
                "Gutiérrez Hernández Herrera Jiménez López Martínez Medina Mendoza Morales Moreno Navarro Oliveira Ortiz "
                "Pereira Pérez Ramírez Rivera Rodríguez Rojas Romero Ruiz Sánchez Santos Silva Torres Vargas Vega",
    },
    "southeast_europe": {
        "weight": 6, "english_first": 0.1,
        "male": "Aleksandar Bojan Burak Davide Dejan Dimitris Dragan Dušan Emre Francesco Gianluca Giorgos Goran Igor "
                "Ioannis Kerem Kostas Luca Luka Marco Marko Matteo Mehmet Miloš Nemanja Nikola Nikos Paolo Stefan Stefano "
                "Vassilis Vladimir Zoran",
        "female": "Chiara Eleni Elif Francesca Giulia Ivana Jelena Katarina Katerina Marija Milica Sara Teodora Valentina "
                  "Zeynep",
        "last": "Antonopoulos Babić Bianchi Çelik Colombo Conti De Luca Demir Đorđević Esposito Ferrari Galli Georgiou "
                "Greco Horvat Ilić Jovanović Kaya Kovačević Marino Marković Nikolaidis Nikolić Papadopoulos Pappas "
                "Pavlović Petrović Popović Radović Ricci Romano Rossi Russo Stojanović Yılmaz",
    },
    "northwest_europe": {
        "weight": 6, "english_first": 0.15,
        "male": "Antoine Artūras Callum Daan Felix Fraser Hamish Henrik Jonas Julien Kristaps Lars Laurent Lukas Mathieu "
                "Mikael Mindaugas Nicolas Pierre Pieter Rhys Sander Tobias Tomas Vincent",
        "female": "Aoife Astrid Camille Elise Emma Fiona Freya Greta Hanna Ieva Ingrid Isla Léa Lena Marie Saskia Siobhan "
                  "Sophie",
        "last": "Andersson Bakker Bērziņš Bernard Byrne de Vries Dubois Fischer Fournier Fraser Girard Hansen Hoffmann "
                "Jankauskas Jansen Johansson Kazlauskas Larsen Lefebvre Lindqvist MacLeod Meyer Moreau Müller Murray "
                "Nielsen Nilsson O'Connor Ozols Petrauskas Rousseau Schneider van Dijk Visser Weber",
    },
    "africa": {
        "weight": 5, "english_first": 0.35,
        "male": "Abdoulaye Akol Cheikh Chidi Chukwuma Emeka Femi Ibrahima Ikenna Joel Kofi Kwame Mabior Mamadou Moussa "
                "Obinna Oluwaseun Pape Pascal Serge Tunde Yaw",
        "female": "Achol Adaeze Akosua Ama Amara Aminata Awa Chioma Esi Fatou Folake Funmilayo Mariama Ngozi Nyakim",
        "last": "Adeyemi Akinola Asante Balogun Boateng Chukwu Deng Diallo Diop Ekwueme Eze Fall Garang Kuol Mayen Mensah "
                "Ndiaye Nwosu Ogunleye Okafor Okeke Okonkwo Onyeka Owusu Sarr Sow Uzoma",
    },
    "asia_pacific": {
        "weight": 5, "english_first": 0.55,
        "male": "Arjun Daisuke Hao Hiroshi Ji-hoon Jun Kenji Min-jun Ming Rohan Seung-ho Takeshi Vikram Wei",
        "female": "Aiko Hana Ji-yeon Lina Mei Priya Sakura Xiu Ying Yuna",
        "last": "Bautista Chen Choi Cruz Desai Gupta Huang Jung Kim Kumar Le Lee Liu Mehta Nguyen Park Patel Pham Rao Reddy "
                "Reyes Shah Singh Suzuki Takahashi Tanaka Tran Wang Watanabe Wu Yamamoto Zhang",
    },
}


def _words(text: str) -> list[str]:
    # Multi-word surnames (De Luca, de Vries, van Dijk) are kept whole.
    words, out = text.split(), []
    for word in words:
        if out and out[-1] in {"De", "de", "van"}:
            out[-1] = f"{out[-1]} {word}"
        else:
            out.append(word)
    return list(dict.fromkeys(out))


FIRST_NAMES: dict[str, list[str]] = {"male": _words(US_MALE), "female": _words(US_FEMALE)}
for _region in REGIONS.values():
    _region["male"] = _words(_region["male"]) if _region["male"] else FIRST_NAMES["male"]
    _region["female"] = _words(_region["female"]) if _region["female"] else FIRST_NAMES["female"]
    _region["last"] = _words(_region["last"])

ALL_FIRST_NAMES = {
    gender: sorted({name for region in REGIONS.values() for name in region[gender]} | set(FIRST_NAMES[gender]))
    for gender in ("male", "female")
}
ALL_LAST_NAMES = sorted({name for region in REGIONS.values() for name in region["last"]})
assert not set(ALL_FIRST_NAMES["male"]) & set(ALL_FIRST_NAMES["female"]), "a first name is on both gender lists"


def draw_name(rng, gender: str) -> str:
    """One first and last name for a person of this gender, from one regional group."""
    regions = list(REGIONS.values())
    total = sum(region["weight"] for region in regions)
    roll = rng.random() * total
    region = regions[-1]
    for candidate in regions:
        roll -= candidate["weight"]
        if roll <= 0:
            region = candidate
            break
    firsts = FIRST_NAMES[gender] if rng.random() < region["english_first"] else region[gender]
    first = firsts[int(rng.random() * len(firsts)) % len(firsts)]
    last = region["last"][int(rng.random() * len(region["last"])) % len(region["last"])]
    return f"{first} {last}"


def first_name_gender(name: str) -> str | None:
    first = str(name or "").split(" ")[0]
    for gender in ("male", "female"):
        if first in ALL_FIRST_NAMES[gender]:
            return gender
    return None
