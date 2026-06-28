import asyncio
import logging
import random
import time

from database import (
    is_listing_posted, mark_listing_posted, get_config, set_config, create_vehicle, create_trailer,
    create_house_listing, get_house_type, get_all_house_types, get_all_neighborhoods,
    get_neighborhood, HOUSE_TYPE_NEIGHBORHOODS, NEIGHBORHOODS,
    is_model_recently_posted, mark_model_posted, clean_old_model_posts,
    get_all_rented_houses, collect_rent,
    get_all_rented_cars, collect_car_rent,
)

logger = logging.getLogger(__name__)

COLORS = [
    "Белый", "Чёрный", "Серебристый", "Серый", "Синий", "Красный",
    "Тёмно-синий", "Зелёный", "Бежевый", "Коричневый", "Бордовый",
    "Золотистый", "Оранжевый", "Жёлтый", "Фиолетовый", "Хаки",
]

GREENVILLE_CARS_BUDGET = [
    ('Auburn', 'Skipper'),
    ('Auburn', 'L3'),
    ('BITSY', 'Classic'),
    ('Auburn', 'Greenwich'),
    ('Durant', 'L/M 1500'),
    ('Durant', 'L/M 2500'),
    ('Mayflower', 'Orbiter'),
    ('Stuttgart', 'Uhlenhaut'),
    ('Arrow', 'Phoenix'),
    ('Avanta', 'Zeta Spacewagon'),
    ('Bayro', 'Series30 Sedan'),
    ('Bayro', 'Series30 Wagon'),
    ('Bayro', 'Series30 Coupe'),
    ('Mazuku', 'Laguna'),
    ('WeGo', 'Coral'),
    ('Brawnson', 'B1500'),
    ('Overland', 'Navajo'),
    ('Western', 'Mamba'),
    ('Western', 'Mamba Plus'),
    ('Renault', 'Twingo'),
    ('Volzhsky', 'Rocket'),
    ('Falcon', 'Scavenger'),
    ('Globe', 'City'),
    ('Newcar', 'Falcata'),
    ('Sunray', 'Thrust Electric Vehicle'),
    ('Viking', 'Torslanda Sedan'),
    ('Viking', 'Torslanda Wagon'),
    ('Western', 'Cervid'),
    ('Western', 'Python'),
    ('Wolfsburg', 'Charge'),
    ('Falcon', 'Advance'),
    ('Falcon', 'Traveller'),
    ('Mizushima', 'Syzygy'),
    ('Navara', 'Summit'),
    ('Sentinel', 'Parliament'),
    ('Mayflower', 'Villager'),
    ('Falcon', 'Stallion'),
    ('Caseus', 'Imperator'),
    ('Falcon', 'Aquarius'),
    ('Shizuoka', 'Slick Coupe'),
    ('Shizuoka', 'Slick Hatchback'),
    ('Shizuoka', 'Slick Sedan'),
    ('Wolfsburg', 'Pitch'),
    ('Combi', 'Satisfaction'),
    ('Falcon', 'Distinct'),
    ('Sentinel', 'Eurus'),
    ('Falcon', 'Wanderer'),
    ('Western', 'Wendigo'),
    ('Falcon', 'Breeze'),
    ('Falcon', 'Departure'),
    ('Maverick', 'Hiker'),
    ('Shizuoka', 'Vision'),
    ('Wolfsburg', 'New Classic'),
    ('Aikawa', 'Neptune'),
    ('Elgrand', 'Horizon'),
    ('Falcon', 'Scavenger Pro-Trip'),
    ('Overland', 'Apache'),
    ('Falcon', 'Advance Pro'),
    ('Leland', 'DeRoute'),
    ('Shizuoka', 'Compound'),
    ('Sumo', 'Woodlands'),
    ('Maverick', 'Valiant'),
    ('Overland', 'Buckaroo'),
    ('Shizuoka', 'Chief'),
    ('Sumo', 'Ota Sedan'),
    ('Sumo', 'Ota Wagon'),
    ('Sumo', 'Rockies'),
    ('Falcon', 'Prime'),
    ('Maverick', 'Aristocrat'),
    ('Mazuku', 'Yushu Performance'),
    ('Idea', 'Twofer'),
    ('Mazuku', 'Sankakkei'),
    ('Navara', 'Adventure'),
    ('Navara', 'Imperium'),
    ('Rokuta', 'Amethyst'),
    ('Takeo', 'Turismo'),
    ('Wolfsburg', 'Glide'),
    ('Wolfsburg', 'Sprint'),
    ('Falcon', 'Angle'),
    ('Mazuku', 'Hofu'),
    ('Mizushima', 'Honor'),
    ('Viking', 'Gothenburg'),
    ('Viking', 'Kompakt'),
    ('Wolfsburg', 'Crouton'),
    ('Wolfsburg', 'Glide Combi'),
    ('Bayro', 'Series50'),
    ('Bayro', 'Series50 Wagon'),
    ('Eezee', 'GML'),
    ('Eezee', 'GML E'),
    ('Maverick', 'Sailor'),
    ('Stuttgart', 'E-Saloon'),
    ('Bayro', 'Series10'),
    ('Bayro', 'e10'),
    ('Durant', 'Venice'),
    ('Falcon', 'Fission'),
    ('Navara', 'Imperium Coupe'),
    ('Viking', 'Obundet'),
    ('Vision', 'Prima'),
    ('Wolfsburg', 'Handel'),
    ('Falcon', 'Distinct Hatchback'),
    ('Falcon', 'Distinct Sedan'),
    ('Wolfsburg', 'Tornado'),
    ('Lawn-King', 'G50X'),
    ('Navara', 'Prism'),
    ('TONY', 'Cinco'),
    ('Navara', 'Eco'),
    ('Wolfsburg', 'Raven'),
]

GREENVILLE_CARS_MID = [
    ('Arrow', 'Executive'),
    ('Wolfsburg', 'Van'),
    ('Wolfsburg', 'Classic'),
    ('Durant', 'Amigo'),
    ('Leland', 'Diamante'),
    ('Falcon', 'Pony'),
    ('Navara', 'Star'),
    ('Wynne', 'Model-12'),
    ('Brawnson', 'Noble Sport'),
    ('Avanta', 'Zeta Coupe'),
    ('Avanta', 'Zeta Sedan'),
    ('Navara', 'Horizon'),
    ('Ferdinand', 'Tourer'),
    ('Mazuku', 'Sankakkei'),
    ('Ferdinand', 'Roadster'),
    ('Maverick', 'Criminal'),
    ('Sumo', 'Boxas'),
    ('Falcon', 'Fowarder'),
    ('Mizushima', 'Yari'),
    ('Sumo', 'Woodlands SPT'),
    ('Vision', 'Dominator'),
    ('Marlin Motors', 'Velindre'),
    ('Arrow', 'Boomerang'),
    ('Celestial', 'Type-1'),
    ('Bayro', 'W50'),
    ('Bayro', 'W50 Wagon'),
    ('Stuttgart', 'E-Saloon 063'),
    ('Oland', 'Exekutiv'),
    ('Celestial', 'Type-5'),
    ('Cobalt', 'Pursuiter'),
    ('Ferdinand', 'Jalapeno'),
    ('Falcon', 'Scavenger'),
    ('Marlin Motors', 'Swan'),
    ('Sentinel', 'Adventurer'),
    ('Falcon', 'Advance'),
    ('Jaguar', 'XJ-L'),
    ('Navara', 'Beat Navmo'),
    ('Overland', 'Buckaroo'),
    ('Sentinel', 'Encouragement'),
    ('Stuttgart', 'Kasten'),
    ('Mizushima', 'Yari Evolution'),
    ('Stuttgart', 'Kecskemét'),
    ('Stuttgart', 'Kecskemét 45'),
    ('Stuttgart', 'Vance'),
    ('Stuttgart', 'Vance 63'),
    ('Sumo', 'Climax'),
    ('Bandit', 'Predator'),
    ('Bandit', 'Ute'),
    ('Sumo', 'Trailstar'),
    ('Viking', 'Torslanda Wagon'),
    ('Vision', 'Puremia'),
    ('Wolfsburg', 'Pitch SportWagen'),
    ('Falcon', 'Advance Pro'),
    ('Falcon', 'Stallion'),
    ('Stuttgart', 'Essen'),
    ('Stuttgart', 'Essen Coupe'),
    ('Stuttgart', 'Executive'),
    ('Stuttgart', 'Jogger 2500'),
    ('Stuttgart', 'Koblenz'),
    ('Sumo', 'Ota'),
    ('TONY', 'Ciento'),
    ('Vision', 'Rainier'),
    ('Wolfsburg', 'Karen'),
    ('Wolfsburg', 'Tornado'),
    ('Falcon', 'Impact'),
    ('Renault', 'Megane R.S.'),
    ('Wolfsburg', 'Handel'),
    ('Wolfsburg', 'Poseidon'),
    ('Celestial', 'Type-4'),
    ('Falcon', 'Departure'),
    ('Falcon', 'Fission'),
    ('Stuttgart', 'Allgau'),
    ('Wolfsburg', 'Pitch'),
    ('Wolfsburg', 'Pitch Alltrack'),
    ('Acadia', 'Syzygy'),
    ('Bayro', 'Series30'),
    ('Bayro', 'Series30 Wagon'),
    ('Bayro', 'Y50'),
    ('Bayro', 'Y60'),
    ('Caseus', 'E2'),
    ('Celestial', 'Type-6'),
    ('Durant', 'Camion'),
    ('Mazuku', 'Kazoku'),
    ('Mizushima', 'Fantasy'),
    ('Mizushima', 'Syzygy Cross'),
    ('Navara', 'Compact'),
    ('Navara', 'Senses'),
    ('Navara', 'Swindler'),
    ('Overland', 'Apache'),
    ('Sentinel', 'Platinum'),
    ('Sumo', 'Woodlands'),
    ('Viking', 'Ghent'),
    ('Viking', 'Torslanda Sedan'),
    ('Vision', 'Prairie'),
    ('Vision', 'Prairie 2500HD'),
    ('Bayro', 'Series40'),
    ('Elgrand', 'Aspect'),
    ('Falcon', 'Wanderer'),
    ('Mazuku', 'Hiro'),
    ('Mazuku', 'Hofu'),
    ('Mazuku', 'Yushu Sedan'),
    ('Navara', 'Boundary'),
    ('Navara', 'Imperium'),
    ('Overland', 'Combatant'),
    ('Overland', 'Navajo'),
    ('Romalpha', 'Julie Quadluck'),
    ('Western', 'Mamba'),
    ('Western', 'Python'),
    ('Wolfsburg', 'Symphony'),
    ('Wolfsburg', 'Tijuana'),
    ('Bayro', 'Series40 Grand Tourer'),
    ('Colt', 'Riolu'),
    ('DIRECT', 'D2'),
    ('Elgrand', 'Perception'),
    ('Elgrand', 'Smyrna'),
    ('Falcon', 'Rampage'),
    ('Falcon', 'Rampage Sport'),
    ('GIGA', 'G3'),
    ('Mazuku', 'Laguna'),
    ('Mizushima', 'Frontier'),
    ('Navara', 'Squadron'),
    ('Navara', 'Summit'),
    ('Overland', 'Apache L'),
    ('Romalpha', 'Steve'),
    ('Sentinel', 'Raider'),
    ('Sumo', 'Asight'),
    ('Sumo', 'Rockies'),
    ('Western', 'Protogen'),
    ('Western', 'Protogen-X'),
    ('Wolfsburg', 'Discovery'),
    ('Wolfsburg', 'Tesuque'),
    ('Century', 'Active'),
    ('Century', 'Nebula'),
    ('Combi', 'Hornet'),
    ('DejaVu', 'Comet'),
    ('Bandit', 'Advance'),
    ('Falcon', 'Cowboy'),
    ('Falcon', 'eStallion'),
    ('Navara', 'Territory'),
    ('Rokuta', 'Amethyst'),
    ('Shizuoka', 'Slick'),
    ('Shizuoka', 'Slick Hatchback'),
    ('Shizuoka', 'Slick Spec-X'),
    ('Viking', 'Kiruna'),
    ('Vision', 'Pioneer'),
    ('Vision', 'Prima'),
    ('Vision', 'Prima Aqua-Cell'),
    ('Vision', 'Riptide Freedom'),
    ('Western', 'Kobold'),
    ('Wolfsburg', 'Pioneer'),
    ('Wolfsburg', 'Poseidon Sportback'),
    ('Acadia', 'TSR'),
    ('Acadia', 'Yari'),
    ('Bandit', 'Advance Storm'),
    ('Celestial', 'Type-4 Overland'),
    ('Colt', 'Vulpes'),
    ('Combi', 'Sei'),
    ('Mazuku', 'Sendai'),
    ('Mazuku', 'Sendai PHEV'),
    ('Shizuoka', 'Alliance'),
    ('Tuscani', 'Euphoria'),
    ('Tuscani', 'Euphoria M'),
    ('Vision', 'Riptide'),
    ('Century', 'Moonlight'),
    ('Shizuoka', 'Hobby'),
    ('Tuscani', 'Rio Grande'),
    ('Tuscani', 'Rio Grande Electrified'),
    ('Western', 'Leviathan'),
    ('Combi', 'Karman'),
    ('Western', 'Sergal'),
    ('Western', 'Sergal Convertible'),
    ('Explorer', 'Dependable 4300 Tow Truck'),
    ('Falcon', 'Global Ambulance'),
]

GREENVILLE_CARS_PREMIUM = [
    ('Mayflower', 'Rage'),
    ('Jaguar', 'E-Type'),
    ('Silhouette', 'Veloce'),
    ('Falcon', 'Stallion'),
    ('Renault', '5'),
    ('Bayro', 'W10'),
    ('Ferdinand', 'Rapido'),
    ('Bayro', 'W30 Sedan'),
    ('Bayro', 'W30 Wagon'),
    ('Bayro', 'W30 Coupe'),
    ('Overland', 'Iroquois'),
    ('Ferdinand', 'Tourer'),
    ('Land Rover', 'Defender'),
    ('Mazuku', 'Sankakkei'),
    ('Navara', 'Horizon GT-R Series-II'),
    ('Renault', 'Clio II'),
    ('Falcon', 'Heritage'),
    ('Stuttgart', 'GT Surrey'),
    ('Eezee', 'Ziggy'),
    ('Navara', 'Horizon'),
    ('Sir Rodgers', 'Zenith'),
    ('Silhouette', 'Gioiosa'),
    ('Silhouette', 'Gioiosa Spyder'),
    ('DejaVu', 'Tradition'),
    ('Surrey', 'Renaissance'),
    ('Celestial', 'Type-1'),
    ('Jaguar', 'XK'),
    ('Stuttgart', 'Sport Falke'),
    ('Jaguar', 'XF'),
    ('Ramsey', '50'),
    ('Surrey', 'LT-500'),
    ('Surrey', 'S-350'),
    ('Stuttgart', 'Koblenz 63'),
    ('Land Rover', 'Range Rover'),
    ('Stuttgart', 'Essen 63'),
    ('Stuttgart', 'Essen 63 Coupe'),
    ('Durant', 'Manta'),
    ('Durant', 'Manta H1000'),
    ('Land Rover', 'Range Rover Sport'),
    ('Leland', 'LCS'),
    ('Leland', 'LCS-V'),
    ('Bayro', 'Y50 W'),
    ('Bayro', 'Y60 W'),
    ('Durant', 'Camion EXT'),
    ('Durant', 'Camion HD'),
    ('Durant', 'Camion DOGG'),
    ('Durant', 'Voyager'),
    ('Land Rover', 'Range Rover Velar'),
    ('Viking', 'Daqing'),
    ('Audi', 'R8 V10 Spyder'),
    ('Bayro', 'W30'),
    ('Marlin Motors', 'Bristol'),
    ('Marlin Motors', 'London'),
    ('Sentinel', 'Adventurer'),
    ('Sentinel', 'Sailor'),
    ('Stuttgart', 'Bruecke'),
    ('Stuttgart', 'Executive'),
    ('Stuttgart', 'Landschaft'),
    ('Stuttgart', 'Sondergeland'),
    ('Stuttgart', 'Sondergeland 63'),
    ('Stuttgart', 'Vaihingen'),
    ('Stuttgart', 'Vaihingen 63'),
    ('Stuttgart', 'Vaihingen 63 Coupe'),
    ('Stuttgart', 'Vaihingen Coupe'),
    ('Stuttgart', 'Vierturig'),
    ('Stuttgart', 'Wilhelm Sondergeland'),
    ('Surrey', 'Grand Tourer'),
    ('Viking', 'Stockholm'),
    ('Bayro', 'W40'),
    ('Celestial', 'Type-5'),
    ('Celestial', 'Type-5 \'Reactive Series\''),
    ('Celestial', 'Type-7'),
    ('Elgrand', 'Immense'),
    ('Ferdinand', 'Cajun'),
    ('Ferdinand', 'Rapido Coupe'),
    ('Ferdinand', 'Rapido GT3'),
    ('Mauntley', 'Cardiff'),
    ('Mauntley', 'Soarer'),
    ('Normouth', 'VN1'),
    ('RELOAD', 'Voltage'),
    ('Sir Rodgers', 'Constellation'),
    ('Stuttgart', 'ES'),
    ('Stuttgart', 'ES 53'),
    ('Stuttgart', 'Sindelfingen'),
    ('Viking', 'Blixt'),
    ('Western', 'SYNTH'),
    ('Audi', 'RS 3'),
    ('Audi', 'RS 5 Sportback'),
    ('Beam', 'SB7'),
    ('Bayro', 'e40'),
    ('Century', 'Nebula 500'),
    ('Colt', 'Okami'),
    ('Bandit', 'Advance Beast'),
    ('Audi', 'RS 6 Avant'),
    ('Falcon', 'Traveller'),
    ('Falcon', 'Traveller Max'),
    ('Ferdinand', 'Snapper'),
    ('Ferdinand', 'Snapper GT4'),
    ('Ferdinand', 'Vivo'),
    ('Ferdinand', 'Vivo CrossWagen'),
    ('Ferdinand', 'Vivo GranWagen'),
    ('Normouth', 'SN-1'),
    ('Normouth', 'TN-1'),
    ('Silhouette', 'Rinoceronte'),
    ('Stuttgart', 'Munster'),
    ('Stuttgart', 'Wilhelm Munster'),
    ('Surrey', 'Ripon'),
    ('Takeo', 'Experience'),
    ('Audi', 'RS 7'),
    ('Bayro', 'Series70'),
    ('Bayro', 'W70'),
    ('Bayro', 'e70'),
    ('Chiara', '006'),
    ('Chiara', 'Vicenzo'),
    ('Colin', 'Commander'),
    ('Normouth', 'VN-1'),
    ('Silhouette', 'Tifon'),
    ('Simple', 'Atmos'),
    ('Sir Rodgers', 'Appiration'),
    ('Vision', 'Dominator'),
    ('Vision', 'Yosemite'),
    ('Audi', 'RS Q8'),
    ('Bayro', 'Y50'),
    ('Bayro', 'Y60'),
    ('Bayro', 'Y70'),
    ('Celestial', 'Type-FS'),
    ('Celestial', 'Type-FT'),
    ('Century', 'Major'),
    ('DIRECT', 'D3'),
    ('Elektrisk', 'Pluto'),
    ('Stuttgart', 'E-Saloon'),
    ('Stuttgart', 'E-Saloon 053'),
    ('Stuttgart', 'Jogger Limo'),
]

MODEL_PRICE_OVERRIDES = {
    ("Globe", "City"): 1500,
    ("Globe", "City L"): 1500,
    ("Chevlon", "Bonneville"): 1850,
    ("BullHorn", "Vivid"): 2000,
    ("Caseus", "Imperator"): 2000,
    ("Chevlon", "Moonfire"): 2000,
    ("Combi", "Satisfaction"): 2000,
    ("Navara", "Pathfinder"): 2100,
    ("Jupiter", "SL1"): 2120,
    ("WeGo", "Coral"): 2189,
    ("Jupiter", "Electron"): 2500,
    ("Mayflower", "Villager"): 2500,
    ("Newcar", "Falcata"): 2500,
    ("BullHorn", "Dash"): 2545,
    ("Arrow", "Orion"): 2700,
    ("Brawnson", "Jimmy"): 2875,
    ("Chryslus", "Voyager"): 2950,
    ("Jupiter", "Alero"): 2950,
    ("Chryslus", "FT Stroller (3-Door)"): 3000,
    ("Chryslus", "FT Stroller (5-Door)"): 3000,
    ("Wolfsburg", "Glide"): 3000,
    ("Arrow", "Starburst"): 3200,
    ("Chevlon", "Aveo Sedan"): 3750,
    ("Arrow", "Grand Prix"): 3950,
    ("Aikawa", "Neptune"): 4000,
    ("Aikawa", "Neptune WSP"): 4000,
    ("BullHorn", "Convoy"): 4000,
    ("BullHorn", "Value"): 4000,
    ("Jupiter", "Ion"): 4225,
    ("Chevlon", "Aveo Hatchback"): 4750,
    ("BullHorn", "Durango"): 4900,
    ("Durant", "Venice"): 4995,
    ("Caseus", "Muenster"): 5000,
    ("Renault", "Twingo"): 5000,
    ("Brawnson", "Sword"): 5200,
    ("Eezee", "GML E"): 5250,
    ("Leland", "DeRoute"): 5500,
    ("Brawnson", "Pretzel"): 5855,
    ("Brawnson", "Boxy"): 6250,
    ("Auburn", "Skipper"): 6500,
    ("Auburn", "Skipper Taxi"): 6500,
    ("Bayro", "Series10"): 6995,
    ("Century", "Excelsior"): 7000,
    ("Auburn", "L3"): 8000,
    ("Auburn", "L3 Plow Truck"): 8000,
    ("BullHorn", "Bullet"): 8000,
    ("Avanta", "Zeta Spacewagon"): 8500,
    ("BullHorn", "Grand Convoy"): 8500,
    ("Arrow", "Trybe"): 9000,
    ("BullHorn", "Toss"): 9500,
    ("BullHorn", "Canaveral"): 9550,
    ("BullHorn", "Vengence"): 9550,
    ("Bayro", "e10"): 10172,
    ("Bayro", "Regen Convertible"): 10295,
    ("Bayro", "Series50"): 10450,
    ("Brawnson", "Baxter"): 10500,
    ("Falcon", "Prime Fire Rescue"): 10500,
    ("Caseus", "E2"): 10999,
    ("Leland", "DeRoute Hearse"): 11435,
    ("BullHorn", "Maximus"): 13000,
    ("BullHorn", "Ninja"): 13000,
    ("Arrow", "Phoenix"): 13190,
    ("Chevlon", "Camion HD"): 13251,
    ("Auburn", "Greenwich"): 13455,
    ("Chevlon", "Antelope"): 13800,
    ("Chevlon", "Platoro"): 14500,
    ("Bayro", "Series50 Wagon"): 14650,
    ("Brawnson", "Land"): 15595,
    ("Chevlon", "Camaro Z28"): 15700,
    ("Caseus", "Tera"): 15750,
    ("Avanta", "Zeta Sedan"): 17000,
    ("Brawnson", "Noble Sedan"): 17500,
    ("Brawnson", "Noble Wagon"): 17500,
    ("Falcon", "Fowarder"): 17500,
    ("Autowerk", "Baden"): 18124,
    ("Leland", "DeRoute Limousine"): 18370,
    ("Arrow", "Executive"): 19355,
    ("Chevlon", "Boom"): 19500,
    ("BKM", "Regen"): 19550,
    ("Bayro", "Series30"): 19750,
    ("Falcon", "Fission"): 19999,
    ("BKM", "Munich"): 20550,
    ("Chevlon", "Sonic Hatchback"): 20690,
    ("Acadia", "Syzygy"): 21500,
    ("Arrow", "Boomerang"): 21678,
    ("Chevlon", "Amigo"): 22000,
    ("Brawnson", "Hockey"): 22375,
    ("APEX", "Deimos GT"): 23000,
    ("Bayro", "Series30 Wagon"): 23450,
    ("Brawnson", "Sierra 3500HD"): 23890,
    ("BullHorn", "Charger RT"): 24000,
    ("BullHorn", "Location"): 24000,
    ("Autowerk", "Ingolstadt"): 24595,
    ("Falcon", "Departure Security"): 25000,
    ("Falcon", "Fission Interceptor"): 25000,
    ("Falcon", "Fission Interceptor Fire Police"): 25000,
    ("Falcon", "Fission Interceptor Security"): 25000,
    ("Brawnson", "Eminence HD"): 25052,
    ("Auburn", "Bullet"): 25750,
    ("Brawnson", "Cicada"): 25930,
    ("Century", "Glider"): 26150,
    ("APEX", "Caprea"): 26500,
    ("BullHorn", "Prancer"): 26595,
    ("Stuttgart", "Vance"): 26972,
    ("Century", "Gemini"): 27500,
    ("Falcon", "Advance Fire Rescue"): 28000,
    ("Chevlon", "GTO"): 29000,
    ("Brawnson", "Plaudit XG"): 29390,
    ("Avanta", "Zeta Coupe"): 29500,
    ("BullHorn", "Determinator"): 29500,
    ("Auburn", "Onward"): 30000,
    ("Barchetta", "Quattroporte"): 30000,
    ("Brawnson", "Noble Sport Coupe"): 30320,
    ("Brawnson", "Kingston"): 30550,
    ("Armstrong", "Denton"): 30900,
    ("Falcon", "Stallion"): 30920,
    ("APEX", "Venator"): 31000,
    ("Brawnson", "Eminence"): 31685,
    ("BullHorn", "Pueblo"): 31857,
    ("Renault", "Megane R.S."): 32500,
    ("Bayro", "Dingolfing IC"): 32560,
    ("Falcon", "Scavenger"): 32920,
    ("Brawnson", "Monsoon"): 33995,
    ("BullHorn", "SuperCarrier"): 34000,
    ("Wolfsburg", "Van"): 34755,
    ("Chevlon", "Captain"): 35000,
    ("Falcon", "Global Ambulance"): 35000,
    ("Barchetta", "GrandTourer"): 35283,
    ("Acadia", "TSR"): 35337,
    ("APEX", "Callisto GT"): 35500,
    ("Autowerk", "Ingolstadt Sedan"): 35550,
    ("Autowerk", "Ingolstadt Sportback"): 35550,
    ("Chryslus", "Consola"): 37095,
    ("Falcon", "Aquarius Security"): 37500,
    ("Brawnson", "Hurricane"): 37824,
    ("Chevlon", "Apex"): 37940,
    ("Bayro", "Olympia Convertible"): 38000,
    ("Brawnson", "Noble"): 38400,
    ("Chevlon", "Belleza"): 38800,
    ("Falcon", "Scavenger Fire Rescue"): 39000,
    ("Falcon", "Scavenger Metro"): 39000,
    ("Falcon", "Scavenger Security"): 39000,
    ("Century", "Meridian"): 39025,
    ("Celestial", "Type-6"): 39490,
    ("Bayro", "W50"): 39800,
    ("Autowerk", "Sulm"): 39900,
    ("Autowerk", "Sulm Avant"): 39900,
    ("Eezee", "GML"): 40000,
    ("Falcon", "Advance DOT"): 40000,
    ("BullHorn", "Buffalo 1500"): 40405,
    ("Celestial", "Type-4"): 40630,
    ("Bayro", "W50 Wagon"): 40800,
    ("Bayro", "Regen"): 41000,
    ("Century", "Active"): 41235,
    ("Explorer", "Dependable 4300 Tow Truck"): 41500,
    ("Stuttgart", "Jogger 2500"): 41500,
    ("Bayro", "Rheine"): 41936,
    ("Stuttgart", "Vance 63"): 41995,
    ("Caline", "C281"): 42000,
    ("Autowerk", "Baden RS"): 42234,
    ("Century", "Moonlight"): 43435,
    ("Autowerk", "Anodic Mosel"): 43900,
    ("Bayro", "Ziggy"): 44450,
    ("Autowerk", "Danube"): 45090,
    ("Leland", "LCS Hearse"): 45230,
    ("Century", "Nebula"): 45945,
    ("Bayro", "Regen Touring"): 46600,
    ("Century", "Aquila"): 47070,
    ("Chevlon", "Calle"): 47500,
    ("Durant", "Camion"): 49064,
    ("Autowerk", "S5"): 49100,
    ("BullHorn", "Buffalo HD"): 50205,
    ("Viking", "Daqing"): 50550,
    ("Renault", "Clio II"): 51200,
    ("Bayro", "Donner Convertible"): 51800,
    ("Bayro", "Regen M Coupe"): 51832,
    ("Autowerk", "Danube Sportback"): 51890,
    ("Autowerk", "Ingolstadt RS"): 51990,
    ("Durant", "Camion EXT"): 52064,
    ("Autowerk", "Tatertot Coupe"): 52140,
    ("Autowerk", "Bremen"): 52547,
    ("Autowerk", "Anodic Mosel Sportback"): 52700,
    ("Sentinel", "Sailor"): 52840,
    ("Stuttgart", "Koblenz 63"): 53500,
    ("Leland", "LCS"): 53690,
    ("Bayro", "Rosenheim"): 54000,
    ("Bayro", "Rosenheim Coupe"): 54000,
    ("Bayro", "Series40"): 54600,
    ("Bayro", "Series40 Grand Tourer"): 54600,
    ("Stuttgart", "Essen 63"): 55007,
    ("Bandit", "Advance Plow DOT Plow"): 55735,
    ("Durant", "Manta"): 55900,
    ("Stuttgart", "Essen 63 Coupe"): 56007,
    ("Autowerk", "Tatertot Roadster"): 56240,
    ("Bayro", "Zoom"): 57400,
    ("Durant", "Camion HD"): 59301,
    ("Bayro", "Hofmeister"): 59420,
    ("Bayro", "Dingolfing M"): 59950,
    ("Bayro", "W10"): 59995,
    ("BullHorn", "Python"): 60000,
    ("Chevlon", "Camion"): 60090,
    ("BullHorn", "Conqueror"): 61352,
    ("Autowerk", "Adelheid"): 62100,
    ("Bayro", "e40"): 62300,
    ("Celestial", "Type-FT"): 62500,
    ("Brawnson", "Arlington"): 63290,
    ("Bayro", "W30"): 63500,
    ("Autowerk", "Ingolstadt RS Sedan"): 63638,
    ("Autowerk", "Ingolstadt RS Sportback"): 63638,
    ("Chevlon", "Camion Ext"): 64090,
    ("Century", "Major"): 64250,
    ("Bayro", "W20"): 65000,
    ("Bayro", "W30 Wagon"): 65500,
    ("Brawnson", "Arlington XL"): 66290,
    ("Bayro", "Y50"): 66600,
    ("Century", "Colonel"): 66922,
    ("Celestial", "Type-FS"): 67500,
    ("Century", "Nebula F"): 67845,
    ("Century", "Nebula 500"): 68320,
    ("Durant", "Voyager"): 68457,
    ("Autowerk", "Bratis"): 70990,
    ("Autowerk", "Anodic"): 72890,
    ("Bayro", "Y60"): 74000,
    ("Autowerk", "Tatertot RS Coupe"): 74245,
    ("Bayro", "Munich"): 74300,
    ("Celestial", "Type-5"): 74990,
    ("Avanta", "Rho"): 75000,
    ("Autowerk", "Bratis Prestiege"): 77500,
    ("Autowerk", "Tatertot RS Roadster"): 78245,
    ("Sentinel", "Adventurer"): 78645,
    ("Autowerk", "Anodic Sportback"): 79590,
    ("Celestial", "Type-7"): 79990,
    ("Barchetta", "Chute"): 81200,
    ("Bayro", "Regen M CSL"): 82955,
    ("Bayro", "eProton"): 83200,
    ("Bayro", "Y70"): 84300,
    ("Bayro", "eRosenheim"): 84500,
    ("Bayro", "Gottfrieding"): 86800,
    ("Bayro", "Olympia M"): 87500,
    ("Mayflower", "Rage"): 87500,
    ("Leland", "LCS-V"): 87990,
    ("Durant", "Camion DOGG"): 89647,
    ("DejaVu", "Tradition"): 90000,
    ("Bayro", "W40"): 90600,
    ("Autowerk", "Anodic GT"): 91540,
    ("Bayro", "Spartanburg"): 92800,
    ("BKM", "Spartanburg"): 94595,
    ("Autowerk", "Sulm RS Avant"): 96182,
    ("Bayro", "Series70"): 96400,
    ("BullHorn", "Location Hellcat Redeye"): 98458,
    ("Bayro", "Regen M"): 101200,
    ("Autowerk", "Bremen VS"): 105389,
    ("Bayro", "e70"): 105700,
    ("Silhouette", "Gioiosa"): 109900,
    ("Navara", "Horizon"): 109990,
    ("Bellco", "Cobra"): 117000,
    ("Bayro", "Donner M Convertible"): 117650,
    ("Autowerk", "Bratis RS"): 123090,
    ("Bayro", "Hofmeister M"): 123870,
    ("Century", "Hawk"): 124000,
    ("Bayro", "Y50 W"): 127200,
    ("Bellco", "SixtySix"): 130000,
    ("Ramsey", "50"): 130000,
    ("Bayro", "Y60 W"): 132100,
    ("Bayro", "Munich M"): 135400,
    ("Bayro", "Risen"): 140000,
    ("Bayro", "Risen Coupe"): 140000,
    ("Silhouette", "Gioiosa Spyder"): 145258,
    ("Autowerk", "Bremen RS"): 148190,
    ("Stuttgart", "Jogger Limo"): 150000,
    ("Autowerk", "LeMans Coupe"): 157490,
    ("Autowerk", "LeMans"): 160000,
    ("Autowerk", "LeMans Spyder"): 161270,
    ("Bayro", "Risen Roadster"): 164600,
    ("Eezee", "Ziggy"): 170000,
    ("Bayro", "Regen M GTS"): 174945,
    ("Stuttgart", "Sport Falke"): 190000,
    ("Surrey", "LT-500"): 198730,
    ("Surrey", "Renaissance"): 203325,
    ("Bayro", "W70"): 220500,
    ("Audi", "R8 V10 Spyder"): 234100,
    ("Bayro", "Olympia"): 250000,
    ("Bayro", "Olympia Coupe"): 250000,
    ("Barchetta", "Corsica"): 256891,
    ("Durant", "Manta H1000"): 265000,
    ("Surrey", "S-350"): 265035,
    ("Silhouette", "Veloce"): 297000,
    ("Falcon", "Fowarder Limo"): 350000,
    ("Stuttgart", "GT Surrey"): 400000,
    ("Sentinel", "Adventurer Limo"): 450000,
    ("Celestial", "FCT"): 450500,
    ("Celestial", "FCT S"): 450500,
    ("Autowerk", "LeMans Anodic"): 485892,
    ("Falcon", "Heritage"): 500000,
    ("Century", "Pinnacle"): 650356,
    ("Surrey", "Speedlet"): 1200000,
    ("Jaguar", "XJ220"): 1500000,
    ("Skane", "Rusa"): 1600000,
    ("Stuttgart", "Munster"): 1800000,
    ("Silhouette", "Attraente"): 1900000,
    ("Saleen", "S7"): 2000000,
    ("Chiara", "Berlinetta GT"): 2200000,
    ("Zephyr", "Vicieux"): 2400000,
    ("Pagani", "Zonda"): 2500000,
    ("Ferdinand", "Ultima"): 2600000,
    ("NVNA", "Acesera"): 2800000,
    ("Pagani", "Huayra"): 2800000,
    ("NVNAsport", "Acesera"): 3000000,
    ("Celestial", "Type-1"): 3500000,
}

GREENVILLE_CARS_LEGENDARY = [
    ('Stuttgart', 'Munster'),
    ('Chiara', 'Berlinetta GT'),
    ('Silhouette', 'Attraente'),
    ('Jaguar', 'XJ220'),
    ('Saleen', 'S7'),
    ('Pagani', 'Zonda'),
    ('Ferdinand', 'Ultima'),
    ('Zephyr', 'Vicieux'),
    ('Pagani', 'Huayra'),
    ('Skane', 'Rusa'),
    ('Surrey', 'Speedlet'),
    ('Celestial', 'Type-1'),
    ('NVNA', 'Acesera'),
    ('NVNAsport', 'Acesera'),
]

LICENSED_CARS = [
    ('Audi', 'R8 V10 Spyder'),
    ('Audi', 'RS 3'),
    ('Audi', 'RS 5 Sportback'),
    ('Audi', 'RS 6 Avant'),
    ('Audi', 'RS 7'),
    ('Audi', 'RS Q8'),
    ('Jaguar', 'E-Type'),
    ('Jaguar', 'XF'),
    ('Jaguar', 'XJ-L'),
    ('Jaguar', 'XJ220'),
    ('Jaguar', 'XK'),
    ('Land Rover', 'Defender'),
    ('Land Rover', 'Range Rover'),
    ('Land Rover', 'Range Rover Sport'),
    ('Land Rover', 'Range Rover Velar'),
    ('Pagani', 'Huayra'),
    ('Pagani', 'Zonda'),
    ('Renault', '5'),
    ('Renault', 'Clio II'),
    ('Renault', 'Megane R.S.'),
    ('Renault', 'Twingo'),
    ('Saleen', 'S7'),
]

LICENSED_BRANDS = {'Saleen', 'Renault', 'Audi', 'Jaguar', 'Land Rover', 'Pagani'}

PURCHASABLE_VEHICLES = {
    'Acadia': [
        'Syzygy',
        'TSR',
        'Yari',
    ],
    'Aikawa': ['Neptune'],
    'Arrow': [
        'Boomerang',
        'Executive',
        'Phoenix',
    ],
    'Auburn': [
        'Greenwich',
        'L3',
        'Skipper',
    ],
    'Audi': [
        'R8 V10 Spyder',
        'RS 3',
        'RS 5 Sportback',
        'RS 6 Avant',
        'RS 7',
        'RS Q8',
    ],
    'Avanta': [
        'Zeta Coupe',
        'Zeta Sedan',
        'Zeta Spacewagon',
    ],
    'BITSY': ['Classic'],
    'Bandit': [
        'Advance',
        'Advance Beast',
        'Advance Storm',
        'Predator',
        'Ute',
    ],
    'Bayro': [
        'Series10',
        'Series30',
        'Series30 Coupe',
        'Series30 Sedan',
        'Series30 Wagon',
        'Series40',
        'Series40 Grand Tourer',
        'Series50',
        'Series50 Wagon',
        'Series70',
        'W10',
        'W30',
        'W30 Coupe',
        'W30 Sedan',
        'W30 Wagon',
        'W40',
        'W50',
        'W50 Wagon',
        'W70',
        'Y50',
        'Y50 W',
        'Y60',
        'Y60 W',
        'Y70',
        'e10',
        'e40',
        'e70',
    ],
    'Beam': ['SB7'],
    'Brawnson': [
        'B1500',
        'Noble Sport',
    ],
    'Caseus': [
        'E2',
        'Imperator',
    ],
    'Celestial': [
        'Type-1',
        'Type-4',
        'Type-4 Overland',
        'Type-5',
        "Type-5 'Reactive Series'",
        'Type-6',
        'Type-7',
        'Type-FS',
        'Type-FT',
    ],
    'Century': [
        'Active',
        'Major',
        'Moonlight',
        'Nebula',
        'Nebula 500',
    ],
    'Chiara': [
        '006',
        'Berlinetta GT',
        'Vicenzo',
    ],
    'Cobalt': ['Pursuiter'],
    'Colin': ['Commander'],
    'Colt': [
        'Okami',
        'Riolu',
        'Vulpes',
    ],
    'Combi': [
        'Hornet',
        'Karman',
        'Satisfaction',
        'Sei',
    ],
    'DIRECT': [
        'D2',
        'D3',
    ],
    'DejaVu': [
        'Comet',
        'Tradition',
    ],
    'Durant': [
        'Amigo',
        'Camion',
        'Camion DOGG',
        'Camion EXT',
        'Camion HD',
        'L/M 1500',
        'L/M 2500',
        'Manta',
        'Manta H1000',
        'Venice',
        'Voyager',
    ],
    'Eezee': [
        'GML',
        'GML E',
        'Ziggy',
    ],
    'Elektrisk': ['Pluto'],
    'Elgrand': [
        'Aspect',
        'Horizon',
        'Immense',
        'Perception',
        'Smyrna',
    ],
    'Falcon': [
        'Advance',
        'Advance Pro',
        'Angle',
        'Aquarius',
        'Breeze',
        'Cowboy',
        'Departure',
        'Distinct',
        'Distinct Hatchback',
        'Distinct Sedan',
        'Fission',
        'Fowarder',
        'Heritage',
        'Impact',
        'Pony',
        'Prime',
        'Rampage',
        'Rampage Sport',
        'Scavenger',
        'Scavenger Pro-Trip',
        'Stallion',
        'Traveller',
        'Traveller Max',
        'Wanderer',
        'eStallion',
        'Global Ambulance',
    ],
    'Ferdinand': [
        'Cajun',
        'Jalapeno',
        'Rapido',
        'Rapido Coupe',
        'Rapido GT3',
        'Roadster',
        'Snapper',
        'Snapper GT4',
        'Tourer',
        'Ultima',
        'Vivo',
        'Vivo CrossWagen',
        'Vivo GranWagen',
    ],
    'GIGA': ['G3'],
    'Globe': ['City'],
    'Idea': ['Twofer'],
    'Jaguar': [
        'E-Type',
        'XF',
        'XJ-L',
        'XJ220',
        'XK',
    ],
    'Land Rover': [
        'Defender',
        'Range Rover',
        'Range Rover Sport',
        'Range Rover Velar',
    ],
    'Lawn-King': ['G50X'],
    'Leland': [
        'DeRoute',
        'Diamante',
        'LCS',
        'LCS-V',
    ],
    'Marlin Motors': [
        'Bristol',
        'London',
        'Swan',
        'Velindre',
    ],
    'Mauntley': [
        'Cardiff',
        'Soarer',
    ],
    'Maverick': [
        'Aristocrat',
        'Criminal',
        'Hiker',
        'Sailor',
        'Valiant',
    ],
    'Mayflower': [
        'Orbiter',
        'Rage',
        'Villager',
    ],
    'Mazuku': [
        'Hiro',
        'Hofu',
        'Kazoku',
        'Laguna',
        'Sankakkei',
        'Sendai',
        'Sendai PHEV',
        'Yushu Performance',
        'Yushu Sedan',
    ],
    'Mizushima': [
        'Fantasy',
        'Frontier',
        'Honor',
        'Syzygy',
        'Syzygy Cross',
        'Yari',
        'Yari Evolution',
    ],
    'NVNA': ['Acesera'],
    'NVNAsport': ['Acesera'],
    'Navara': [
        'Adventure',
        'Beat Navmo',
        'Boundary',
        'Compact',
        'Eco',
        'Horizon',
        'Horizon GT-R Series-II',
        'Imperium',
        'Imperium Coupe',
        'Prism',
        'Senses',
        'Squadron',
        'Star',
        'Summit',
        'Swindler',
        'Territory',
    ],
    'Newcar': ['Falcata'],
    'Normouth': [
        'SN-1',
        'TN-1',
        'VN-1',
        'VN1',
    ],
    'Oland': ['Exekutiv'],
    'Overland': [
        'Apache',
        'Apache L',
        'Buckaroo',
        'Combatant',
        'Iroquois',
        'Navajo',
    ],
    'Pagani': [
        'Huayra',
        'Zonda',
    ],
    'RELOAD': ['Voltage'],
    'Ramsey': ['50'],
    'Renault': [
        '5',
        'Clio II',
        'Megane R.S.',
        'Twingo',
    ],
    'Rokuta': ['Amethyst'],
    'Romalpha': [
        'Julie Quadluck',
        'Steve',
    ],
    'Saleen': ['S7'],
    'Sentinel': [
        'Adventurer',
        'Encouragement',
        'Eurus',
        'Parliament',
        'Platinum',
        'Raider',
        'Sailor',
    ],
    'Shizuoka': [
        'Alliance',
        'Chief',
        'Compound',
        'Hobby',
        'Slick',
        'Slick Coupe',
        'Slick Hatchback',
        'Slick Sedan',
        'Slick Spec-X',
        'Vision',
    ],
    'Silhouette': [
        'Attraente',
        'Gioiosa',
        'Gioiosa Spyder',
        'Rinoceronte',
        'Tifon',
        'Veloce',
    ],
    'Simple': ['Atmos'],
    'Sir Rodgers': [
        'Appiration',
        'Constellation',
        'Zenith',
    ],
    'Skane': ['Rusa'],
    'Stuttgart': [
        'Allgau',
        'Bruecke',
        'E-Saloon',
        'E-Saloon 053',
        'E-Saloon 063',
        'ES',
        'ES 53',
        'Essen',
        'Essen 63',
        'Essen 63 Coupe',
        'Essen Coupe',
        'Executive',
        'GT Surrey',
        'Jogger 2500',
        'Kasten',
        'Kecskemét',
        'Kecskemét 45',
        'Koblenz',
        'Koblenz 63',
        'Landschaft',
        'Munster',
        'Sindelfingen',
        'Sondergeland',
        'Sondergeland 63',
        'Sport Falke',
        'Uhlenhaut',
        'Vaihingen',
        'Vaihingen 63',
        'Vaihingen 63 Coupe',
        'Vaihingen Coupe',
        'Vance',
        'Vance 63',
        'Vierturig',
        'Wilhelm Munster',
        'Wilhelm Sondergeland',
        'Jogger Limo',
    ],
    'Sumo': [
        'Asight',
        'Boxas',
        'Climax',
        'Ota',
        'Ota Sedan',
        'Ota Wagon',
        'Rockies',
        'Trailstar',
        'Woodlands',
        'Woodlands SPT',
    ],
    'Sunray': ['Thrust Electric Vehicle'],
    'Explorer': ['Dependable 4300 Tow Truck'],
    'Surrey': [
        'Grand Tourer',
        'LT-500',
        'Renaissance',
        'Ripon',
        'S-350',
        'Speedlet',
    ],
    'TONY': [
        'Ciento',
        'Cinco',
    ],
    'Takeo': [
        'Experience',
        'Turismo',
    ],
    'Tuscani': [
        'Euphoria',
        'Euphoria M',
        'Rio Grande',
        'Rio Grande Electrified',
    ],
    'Viking': [
        'Blixt',
        'Daqing',
        'Ghent',
        'Gothenburg',
        'Kiruna',
        'Kompakt',
        'Obundet',
        'Stockholm',
        'Torslanda Sedan',
        'Torslanda Wagon',
    ],
    'Vision': [
        'Dominator',
        'Pioneer',
        'Prairie',
        'Prairie 2500HD',
        'Prima',
        'Prima Aqua-Cell',
        'Puremia',
        'Rainier',
        'Riptide',
        'Riptide Freedom',
        'Yosemite',
    ],
    'Volzhsky': ['Rocket'],
    'WeGo': ['Coral'],
    'Western': [
        'Cervid',
        'Kobold',
        'Leviathan',
        'Mamba',
        'Mamba Plus',
        'Protogen',
        'Protogen-X',
        'Python',
        'SYNTH',
        'Sergal',
        'Sergal Convertible',
        'Wendigo',
    ],
    'Wolfsburg': [
        'Charge',
        'Classic',
        'Crouton',
        'Discovery',
        'Glide',
        'Glide Combi',
        'Handel',
        'Karen',
        'New Classic',
        'Pioneer',
        'Pitch',
        'Pitch Alltrack',
        'Pitch SportWagen',
        'Poseidon',
        'Poseidon Sportback',
        'Raven',
        'Sprint',
        'Symphony',
        'Tesuque',
        'Tijuana',
        'Tornado',
        'Van',
    ],
    'Wynne': ['Model-12'],
    'Zephyr': ['Vicieux'],
}

PURCHASABLE_SET = {(make.lower(), model.lower()) for make, models in PURCHASABLE_VEHICLES.items() for model in models}

BRAND_TO_REAL = {
    'Acadia': 'Mitsubishi',
    'Aikawa': 'Isuzu',
    'Andre': 'Fictional',
    'Arrow': 'Pontiac',
    'Auburn': 'Auburn',
    'Audi': 'Audi',
    'Autowerk': 'Audi',
    'Avanta': 'Fictional',
    'BITSY': 'MINI',
    'Bandit': 'Ford',
    'Bayro': 'Alpina',
    'Beam': 'NIO',
    'Bob': 'Fictional',
    'Brawnson': 'GMC',
    'Caseus': 'Fictional',
    'Celestial': 'Tesla',
    'Century': 'Lexus',
    'Chiara': 'Ferrari',
    'Cobalt': 'Carbon Motors',
    'Colin': 'Fictional',
    'Colt': 'Fictional',
    'Combi': 'Kia',
    'DIRECT': 'Fictional',
    'DejaVu': 'Fisker',
    'Durant': 'Chevrolet',
    'Eezee': 'EZ-GO',
    'Elektrisk': 'Fictional',
    'Elgrand': 'Infiniti',
    'Falcon': 'Ford',
    'Ferdinand': 'Porsche',
    'GIGA': 'Lynk&Co',
    'Globe': 'Geo',
    'Idea': 'Smart',
    'Jaguar': 'Jaguar',
    'Land Rover': 'Land Rover',
    'Lawn King': 'Fictional',
    'Lawn-King': 'Fictional',
    'LawnKing': 'Fictional',
    'Leland': 'Cadillac',
    'Marlin': 'Fictional',
    'Marlin Motors': 'Aston Martin',
    'Mauntley': 'Bentley',
    'Maverick': 'Mercury',
    'Mayflower': 'Plymouth',
    'Mazuku': 'Mazda',
    'Mizushima': 'Mitsubishi',
    'NVNA': 'Fictional',
    'NVNAsport': 'Fictional',
    'Navara': 'Nissan',
    'Newcar': 'Oldsmobile',
    'Normouth': 'Rivian',
    'Oland': 'Fictional',
    'Overland': 'Jeep',
    'Pagani': 'Pagani',
    'Piranha': 'Fictional',
    'RELOAD': 'Fictional',
    'Ramsey': 'Peel',
    'Renault': 'Renault',
    'Rokuta': 'Fictional',
    'Romalpha': 'Alfa Romeo',
    'Rovelo': 'Fictional',
    'Saleen': 'Saleen',
    'Sentinel': 'Lincoln',
    'Shizuoka': 'Honda',
    'Silhouette': 'Lamborghini',
    'Simple': 'Lucid',
    'Sir Rodgers': 'Rolls-Royce',
    'SirRodgers': 'Rolls-Royce',
    'Skane': 'Koenigsegg',
    'Stuttgart': 'Mercedes-Benz',
    'Sumo': 'Subaru',
    'Sunray': 'Fictional',
    'Surrey': 'McLaren',
    'TONY': 'Fictional',
    'Takeo': 'Acura',
    'TerrainTraveller': 'Fictional',
    'Tuscani': 'Hyundai',
    'Viking': 'Volvo',
    'Vision': 'Toyota',
    'Volt': 'Fictional',
    'Volzhsky': 'Lada',
    'WeGo': 'Fictional',
    'Western': 'Fictional',
    'Wolfsburg': 'Volkswagen',
    'Wynne': 'Fictional',
    'Zephyr': 'Fictional',
}

REAL_BRAND_VALUE = {
    'Audi': 3,
    'Autowerk': 3,
    'BITSY': 1.8,
    'Century': 3,
    'Chiara': 14,
    'Colt': 2,
    'DejaVu': 3,
    'Ferdinand': 5.5,
    'GIGA': 2,
    'Jaguar': 3.5,
    'Land Rover': 3.5,
    'Leland': 3,
    'Marlin Motors': 7,
    'Mauntley': 10,
    'Normouth': 5,
    'Pagani': 20,
    'Ramsey': 5,
    'Renault': 1.5,
    'Romalpha': 2.5,
    'Saleen': 3.5,
    'Sentinel': 2.5,
    'Silhouette': 14,
    'Simple': 5,
    'Sir Rodgers': 10,
    'SirRodgers': 10,
    'Skane': 18,
    'Stuttgart': 4,
    'Surrey': 12,
    'Takeo': 3,
    'Viking': 2,
}

def is_purchasable(make: str, model: str) -> bool:
    return (make.lower(), model.lower()) in PURCHASABLE_SET

COMMON_CARS = GREENVILLE_CARS_BUDGET + GREENVILLE_CARS_MID[:20]  # больше разнообразия
RARE_CARS = GREENVILLE_CARS_MID[20:] + GREENVILLE_CARS_PREMIUM
LEGENDARY_CARS = GREENVILLE_CARS_LEGENDARY

YEARS = list(range(1995, 2026))

WI_CITIES_RU = [
    "Милуоки", "Мадисон", "Грин-Бей", "Апплтон", "О-Клэр", "Кеноша",
    "Расин", "Ла-Кросс", "Шебойган", "Восау", "Джейнсвилл",
    "Фонд-дю-Лак", "Белоит", "Манитовок", "Ошкош", "Стивенс-Пойнт",
]

CONDITIONS = ["отличное", "хорошее", "очень хорошее", "обслужена", "без нареканий", "ездит отлично"]
DAMAGED_CONDITIONS = ["битая", "после ДТП", "не на ходу", "тотал", "срочно на запчасти", "гнилая"]

FEATURES = ["климат-контроль", "подогрев сидений", "Bluetooth", "камера заднего вида",
    "кожаный салон", "полный привод (AWD)", "люк", "парктроники",
    "бесключевой доступ", "круиз-контроль", "CarPlay", "сигнализация", "тонировка",
    "новые шины", "ABS, ESP", "датчики дождя и света"]
TITLES = ["чистый", "в наличии", "срочно", "торг уместен", "обмен не интересует"]

DAMAGED_TITLES = ["битый", "нерабочий", "на запчасти", "срочно", "в ремонт"]

WORK_VEHICLES = [
    ('Wolfsburg', 'Van'),
    ('Stuttgart', 'Jogger 2500'),
    ('Stuttgart', 'Jogger Limo'),
    ('Explorer', 'Dependable 4300 Tow Truck'),
    ('Falcon', 'Global Ambulance'),
    ('Falcon', 'Advance DOT'),
    ('Falcon', 'Advance Fire Rescue'),
    ('Bandit', 'Advance Plow DOT Plow'),
    ('Falcon', 'Departure Security'),
    ('Falcon', 'Prime Fire Rescue'),
    ('Falcon', 'Scavenger Fire Rescue'),
    ('Falcon', 'Scavenger Metro'),
    ('Falcon', 'Scavenger Security'),
    ('Falcon', 'Aquarius Security'),
    ('Falcon', 'Fission Interceptor Fire Police'),
    ('Falcon', 'Fission Interceptor Security'),
    ('Falcon', 'Fowarder Limo'),
    ('Leland', 'DeRoute Hearse'),
    ('Leland', 'DeRoute Limousine'),
    ('Leland', 'LCS Hearse'),
    ('Durant', 'Camion'),
    ('Durant', 'Camion EXT'),
    ('Durant', 'Camion HD'),
    ('Durant', 'Voyager'),
    ('Sentinel', 'Adventurer Limo'),
]

RARITY_WEIGHTS = {"common": 65, "damaged": 8, "rare": 18, "legendary": 9}
RARITY_MULTIPLIERS = {"common": 1.0, "damaged": 0.3, "rare": 1.5, "legendary": 1.0}

CAR_POOL = {}
for _c in GREENVILLE_CARS_BUDGET:
    CAR_POOL[_c] = "budget"
for _c in GREENVILLE_CARS_MID:
    CAR_POOL[_c] = "mid"
for _c in GREENVILLE_CARS_PREMIUM:
    CAR_POOL[_c] = "premium"
for _c in GREENVILLE_CARS_LEGENDARY:
    CAR_POOL[_c] = "legendary"
for _c in WORK_VEHICLES:
    CAR_POOL[_c] = "work"
for _c in LICENSED_CARS:
    CAR_POOL[_c] = "licensed"

POOL_BASE_PRICE = {
    "budget": 5000,
    "mid": 25000,
    "premium": 80000,
    "legendary": 2000000,
    "work": 35000,
    "licensed": 60000,
}

RARITY_NAMES = {"common": "", "damaged": "💥 Битый", "rare": "⭐ Редкий", "legendary": "🔥🔥🔥 МЕГА-КАР 🔥🔥🔥"}
CAR_YEARS = {
    ('Acadia', 'Syzygy'): {2020},
    ('Acadia', 'TSR'): {2024},
    ('Acadia', 'Yari'): {2024},
    ('Aikawa', 'Neptune'): {2004},
    ('Arrow', 'Boomerang'): {2008},
    ('Arrow', 'Executive'): {1953},
    ('Arrow', 'Phoenix'): {1988},
    ('Auburn', 'Greenwich'): {1966},
    ('Auburn', 'L3'): {1953},
    ('Auburn', 'Skipper'): {1940, 1957},
    ('Audi', 'R8 V10 Spyder'): {2021},
    ('Audi', 'RS 3'): {2023},
    ('Audi', 'RS 5 Sportback'): {2023},
    ('Audi', 'RS 6 Avant'): {2025},
    ('Audi', 'RS 7'): {2024},
    ('Audi', 'RS Q8'): {2025},
    ('Avanta', 'Zeta Coupe'): {1988},
    ('Avanta', 'Zeta Sedan'): {1988},
    ('Avanta', 'Zeta Spacewagon'): {1988},
    ('BITSY', 'Classic'): {1963, 2006},
    ('Bandit', 'Advance'): {2023},
    ('Bandit', 'Advance Beast'): {2023},
    ('Bandit', 'Advance Storm'): {2024},
    ('Bandit', 'Predator'): {2016},
    ('Bandit', 'Ute'): {2016},
    ('Bayro', 'Series10'): {2012},
    ('Bayro', 'Series30'): {2020},
    ('Bayro', 'Series30 Coupe'): {1990},
    ('Bayro', 'Series30 Sedan'): {1990},
    ('Bayro', 'Series30 Wagon'): {1990, 2020},
    ('Bayro', 'Series40'): {2021},
    ('Bayro', 'Series40 Grand Tourer'): {2022},
    ('Bayro', 'Series50'): {2010},
    ('Bayro', 'Series50 Wagon'): {2010},
    ('Bayro', 'Series70'): {2024},
    ('Bayro', 'W10'): {1981, 2012},
    ('Bayro', 'W30'): {2021},
    ('Bayro', 'W30 Coupe'): {1990},
    ('Bayro', 'W30 Sedan'): {1990},
    ('Bayro', 'W30 Wagon'): {1990, 2021},
    ('Bayro', 'W40'): {2022},
    ('Bayro', 'W50'): {2010},
    ('Bayro', 'W50 Wagon'): {2010},
    ('Bayro', 'W70'): {2024},
    ('Bayro', 'Y50'): {2020, 2025},
    ('Bayro', 'Y50 W'): {2020, 2025},
    ('Bayro', 'Y60'): {2020, 2025},
    ('Bayro', 'Y60 W'): {2020, 2025},
    ('Bayro', 'Y70'): {2025},
    ('Bayro', 'e10'): {2012},
    ('Bayro', 'e40'): {2023},
    ('Bayro', 'e70'): {2024},
    ('Beam', 'SB7'): {2023},
    ('Brawnson', 'B1500'): {1992},
    ('Brawnson', 'Noble Sport'): {1986},
    ('Caseus', 'E2'): {2020},
    ('Caseus', 'Imperator'): {2000},
    ('Celestial', 'Type-1'): {2008, 2013, 2023},
    ('Celestial', 'Type-4'): {2019, 2023},
    ('Celestial', 'Type-4 Overland'): {2024},
    ('Celestial', 'Type-5'): {2012, 2013, 2018, 2022, 2025},
    ('Celestial', 'Type-6'): {2020, 2024},
    ('Celestial', 'Type-7'): {2022, 2025},
    ('Celestial', 'Type-FS'): {2025},
    ('Celestial', 'Type-FT'): {2025},
    ('Century', 'Active'): {2023},
    ('Century', 'Major'): {2025},
    ('Century', 'Moonlight'): {2025},
    ('Century', 'Nebula'): {2023},
    ('Century', 'Nebula 500'): {2023},
    ('Chiara', '006'): {2024},
    ('Chiara', 'Berlinetta GT'): {1962},
    ('Chiara', 'Vicenzo'): {2024},
    ('Cobalt', 'Pursuiter'): {2012},
    ('Colin', 'Commander'): {2024},
    ('Colt', 'Okami'): {2023},
    ('Colt', 'Riolu'): {2022, 2024},
    ('Colt', 'Vulpes'): {2024},
    ('Combi', 'Hornet'): {2023},
    ('Combi', 'Karman'): {2026},
    ('Combi', 'Satisfaction'): {2001},
    ('Combi', 'Sei'): {2024},
    ('DIRECT', 'D2'): {2022, 2024},
    ('DIRECT', 'D3'): {2025},
    ('DejaVu', 'Comet'): {2023},
    ('DejaVu', 'Tradition'): {2012, 2019},
    ('Durant', 'Amigo'): {1969},
    ('Durant', 'Camion'): {2020},
    ('Durant', 'Camion DOGG'): {2020},
    ('Durant', 'Camion EXT'): {2020},
    ('Durant', 'Camion HD'): {2020},
    ('Durant', 'L/M 1500'): {1971},
    ('Durant', 'L/M 2500'): {1971},
    ('Durant', 'Manta'): {2019},
    ('Durant', 'Manta H1000'): {2019},
    ('Durant', 'Venice'): {2012},
    ('Durant', 'Voyager'): {2020},
    ('Eezee', 'GML'): {2010},
    ('Eezee', 'GML E'): {2010},
    ('Eezee', 'Ziggy'): {2008},
    ('Elektrisk', 'Pluto'): {2025},
    ('Elgrand', 'Aspect'): {2021},
    ('Elgrand', 'Horizon'): {2004, 2006, 2008},
    ('Elgrand', 'Immense'): {2022},
    ('Elgrand', 'Perception'): {2022},
    ('Elgrand', 'Smyrna'): {2022},
    ('Explorer', 'Dependable 4300 Tow Truck'): {2007},
    ('Falcon', 'Advance'): {1998, 2014, 2017, 2019, 2023},
    ('Falcon', 'Advance Pro'): {2005, 2017, 2022},
    ('Falcon', 'Angle'): {2009},
    ('Falcon', 'Aquarius'): {2000, 2006, 2012, 2015},
    ('Falcon', 'Breeze'): {2003},
    ('Falcon', 'Cowboy'): {2023},
    ('Falcon', 'Departure'): {2003, 2010, 2019, 2021},
    ('Falcon', 'Distinct'): {2001, 2008},
    ('Falcon', 'Distinct Hatchback'): {2013, 2017},
    ('Falcon', 'Distinct Sedan'): {2013, 2017},
    ('Falcon', 'Fission'): {2012, 2019},
    ('Falcon', 'Fowarder'): {2005},
    ('Falcon', 'Global Ambulance'): {2013},
    ('Falcon', 'Heritage'): {2005},
    ('Falcon', 'Impact'): {2018},
    ('Falcon', 'Pony'): {1972},
    ('Falcon', 'Prime'): {2007},
    ('Falcon', 'Rampage'): {2022},
    ('Falcon', 'Rampage Sport'): {2022},
    ('Falcon', 'Scavenger'): {1996, 2003, 2013, 2016, 2021},
    ('Falcon', 'Scavenger Pro-Trip'): {2004},
    ('Falcon', 'Stallion'): {1970, 1999, 2007, 2017, 2024},
    ('Falcon', 'Traveller'): {1998, 2006, 2023},
    ('Falcon', 'Traveller Max'): {2023},
    ('Falcon', 'Wanderer'): {2002, 2021},
    ('Falcon', 'eStallion'): {2023},
    ('Ferdinand', 'Cajun'): {2022},
    ('Ferdinand', 'Jalapeno'): {2012},
    ('Ferdinand', 'Rapido'): {1981, 2017},
    ('Ferdinand', 'Rapido Coupe'): {2022},
    ('Ferdinand', 'Rapido GT3'): {2022},
    ('Ferdinand', 'Roadster'): {2004},
    ('Ferdinand', 'Snapper'): {2023},
    ('Ferdinand', 'Snapper GT4'): {2023},
    ('Ferdinand', 'Tourer'): {1990, 1995},
    ('Ferdinand', 'Ultima'): {2007},
    ('Ferdinand', 'Vivo'): {2023},
    ('Ferdinand', 'Vivo CrossWagen'): {2023},
    ('Ferdinand', 'Vivo GranWagen'): {2023},
    ('GIGA', 'G3'): {2022},
    ('Globe', 'City'): {1996},
    ('Idea', 'Twofer'): {2008, 2015},
    ('Jaguar', 'E-Type'): {1961},
    ('Jaguar', 'XF'): {2015},
    ('Jaguar', 'XJ-L'): {2014},
    ('Jaguar', 'XJ220'): {1994},
    ('Jaguar', 'XK'): {2013},
    ('Land Rover', 'Defender'): {1997, 2025},
    ('Land Rover', 'Range Rover'): {2018},
    ('Land Rover', 'Range Rover Sport'): {2019},
    ('Land Rover', 'Range Rover Velar'): {2020},
    ('Lawn-King', 'G50X'): {2014},
    ('Leland', 'DeRoute'): {2005},
    ('Leland', 'Diamante'): {1969},
    ('Leland', 'LCS'): {2019},
    ('Leland', 'LCS-V'): {2019},
    ('Marlin Motors', 'Bristol'): {2021},
    ('Marlin Motors', 'London'): {2021},
    ('Marlin Motors', 'Swan'): {2013},
    ('Marlin Motors', 'Velindre'): {2007},
    ('Mauntley', 'Cardiff'): {2022},
    ('Mauntley', 'Soarer'): {2022},
    ('Maverick', 'Aristocrat'): {2007},
    ('Maverick', 'Criminal'): {2004},
    ('Maverick', 'Hiker'): {2003},
    ('Maverick', 'Sailor'): {2010},
    ('Maverick', 'Valiant'): {2006},
    ('Mayflower', 'Orbiter'): {1971},
    ('Mayflower', 'Rage'): {1958},
    ('Mayflower', 'Villager'): {1999},
    ('Mazuku', 'Hiro'): {2021},
    ('Mazuku', 'Hofu'): {2009, 2021},
    ('Mazuku', 'Kazoku'): {2020},
    ('Mazuku', 'Laguna'): {1990, 2022},
    ('Mazuku', 'Sankakkei'): {1995, 2002, 2008, 2012},
    ('Mazuku', 'Sendai'): {2024},
    ('Mazuku', 'Sendai PHEV'): {2024},
    ('Mazuku', 'Yushu Performance'): {2007},
    ('Mazuku', 'Yushu Sedan'): {2021},
    ('Mizushima', 'Fantasy'): {2020},
    ('Mizushima', 'Frontier'): {2022},
    ('Mizushima', 'Honor'): {2009},
    ('Mizushima', 'Syzygy'): {1998},
    ('Mizushima', 'Syzygy Cross'): {2020},
    ('Mizushima', 'Yari'): {2005},
    ('Mizushima', 'Yari Evolution'): {2015},
    ('NVNA', 'Acesera'): {2023},
    ('NVNAsport', 'Acesera'): {2023},
    ('Navara', 'Adventure'): {2008},
    ('Navara', 'Beat Navmo'): {2014},
    ('Navara', 'Boundary'): {2021},
    ('Navara', 'Compact'): {2020},
    ('Navara', 'Eco'): {2015},
    ('Navara', 'Horizon'): {1989, 2009, 2017},
    ('Navara', 'Horizon GT-R Series-II'): {2002},
    ('Navara', 'Imperium'): {2008, 2013, 2021},
    ('Navara', 'Imperium Coupe'): {2012},
    ('Navara', 'Prism'): {2014},
    ('Navara', 'Senses'): {2020},
    ('Navara', 'Squadron'): {2022},
    ('Navara', 'Star'): {1972, 2008, 2011, 2019, 2022},
    ('Navara', 'Summit'): {1998, 2022},
    ('Navara', 'Swindler'): {2020, 2022},
    ('Navara', 'Territory'): {2023},
    ('Newcar', 'Falcata'): {1996},
    ('Normouth', 'SN-1'): {2023},
    ('Normouth', 'TN-1'): {2023},
    ('Normouth', 'VN-1'): {2024},
    ('Normouth', 'VN1'): {2022},
    ('Oland', 'Exekutiv'): {2011},
    ('Overland', 'Apache'): {2004, 2020},
    ('Overland', 'Apache L'): {2022},
    ('Overland', 'Buckaroo'): {2006, 2014, 2021},
    ('Overland', 'Combatant'): {2021},
    ('Overland', 'Iroquois'): {1991},
    ('Overland', 'Navajo'): {1993, 2001, 2021},
    ('Pagani', 'Huayra'): {2017},
    ('Pagani', 'Zonda'): {2006, 2017},
    ('RELOAD', 'Voltage'): {2022},
    ('Ramsey', '50'): {2015},
    ('Renault', '5'): {1980},
    ('Renault', 'Clio II'): {2003},
    ('Renault', 'Megane R.S.'): {2018},
    ('Renault', 'Twingo'): {1995},
    ('Rokuta', 'Amethyst'): {2008, 2023},
    ('Romalpha', 'Julie Quadluck'): {2021},
    ('Romalpha', 'Steve'): {2022},
    ('Saleen', 'S7'): {2005, 2006},
    ('Sentinel', 'Adventurer'): {2013, 2021},
    ('Sentinel', 'Encouragement'): {2014},
    ('Sentinel', 'Eurus'): {2001},
    ('Sentinel', 'Parliament'): {1998, 2007},
    ('Sentinel', 'Platinum'): {2020},
    ('Sentinel', 'Raider'): {2022},
    ('Sentinel', 'Sailor'): {2021},
    ('Shizuoka', 'Alliance'): {2024},
    ('Shizuoka', 'Chief'): {2006},
    ('Shizuoka', 'Compound'): {2005, 2009},
    ('Shizuoka', 'Hobby'): {2025},
    ('Shizuoka', 'Slick'): {2023},
    ('Shizuoka', 'Slick Coupe'): {2000},
    ('Shizuoka', 'Slick Hatchback'): {2000, 2023},
    ('Shizuoka', 'Slick Sedan'): {2000},
    ('Shizuoka', 'Slick Spec-X'): {2023},
    ('Shizuoka', 'Vision'): {2003},
    ('Silhouette', 'Attraente'): {1986, 1988},
    ('Silhouette', 'Gioiosa'): {2011},
    ('Silhouette', 'Gioiosa Spyder'): {2011},
    ('Silhouette', 'Rinoceronte'): {2023},
    ('Silhouette', 'Tifon'): {2024},
    ('Silhouette', 'Veloce'): {1967},
    ('Simple', 'Atmos'): {2024},
    ('Sir Rodgers', 'Appiration'): {2024},
    ('Sir Rodgers', 'Constellation'): {2022},
    ('Sir Rodgers', 'Zenith'): {2010},
    ('Skane', 'Rusa'): {2018},
    ('Stuttgart', 'Allgau'): {2019},
    ('Stuttgart', 'Bruecke'): {2021},
    ('Stuttgart', 'E-Saloon'): {2010, 2025},
    ('Stuttgart', 'E-Saloon 053'): {2025},
    ('Stuttgart', 'E-Saloon 063'): {2010},
    ('Stuttgart', 'ES'): {2022},
    ('Stuttgart', 'ES 53'): {2022},
    ('Stuttgart', 'Essen'): {2017},
    ('Stuttgart', 'Essen 63'): {2018},
    ('Stuttgart', 'Essen 63 Coupe'): {2018},
    ('Stuttgart', 'Essen Coupe'): {2017},
    ('Stuttgart', 'Executive'): {2017, 2021},
    ('Stuttgart', 'GT Surrey'): {2007},
    ('Stuttgart', 'Jogger 2500'): {2017},
    ('Stuttgart', 'Jogger Limo'): {2017},
    ('Stuttgart', 'Kasten'): {2014},
    ('Stuttgart', 'Kecskemét'): {2015},
    ('Stuttgart', 'Kecskemét 45'): {2015},
    ('Stuttgart', 'Koblenz'): {2017},
    ('Stuttgart', 'Koblenz 63'): {2017},
    ('Stuttgart', 'Landschaft'): {2021},
    ('Stuttgart', 'Munster'): {1955, 2023},
    ('Stuttgart', 'Sindelfingen'): {2022},
    ('Stuttgart', 'Sondergeland'): {2021},
    ('Stuttgart', 'Sondergeland 63'): {2021},
    ('Stuttgart', 'Sport Falke'): {2014},
    ('Stuttgart', 'Uhlenhaut'): {1971},
    ('Stuttgart', 'Vaihingen'): {2021},
    ('Stuttgart', 'Vaihingen 63'): {2021},
    ('Stuttgart', 'Vaihingen 63 Coupe'): {2021},
    ('Stuttgart', 'Vaihingen Coupe'): {2021},
    ('Stuttgart', 'Vance'): {2015},
    ('Stuttgart', 'Vance 63'): {2015},
    ('Stuttgart', 'Vierturig'): {2021},
    ('Stuttgart', 'Wilhelm Munster'): {2023},
    ('Stuttgart', 'Wilhelm Sondergeland'): {2021},
    ('Sumo', 'Asight'): {2022},
    ('Sumo', 'Boxas'): {2004, 2017},
    ('Sumo', 'Climax'): {2015, 2022},
    ('Sumo', 'Ota'): {2017, 2020},
    ('Sumo', 'Ota Sedan'): {2006},
    ('Sumo', 'Ota Wagon'): {2006},
    ('Sumo', 'Rockies'): {2006, 2022},
    ('Sumo', 'Trailstar'): {2016, 2020},
    ('Sumo', 'Woodlands'): {2005, 2018, 2020},
    ('Sumo', 'Woodlands SPT'): {2005},
    ('Sunray', 'Thrust Electric Vehicle'): {1996},
    ('Surrey', 'Grand Tourer'): {2021},
    ('Surrey', 'LT-500'): {2016},
    ('Surrey', 'Renaissance'): {2012},
    ('Surrey', 'Ripon'): {2023},
    ('Surrey', 'S-350'): {2016},
    ('Surrey', 'Speedlet'): {2020},
    ('TONY', 'Ciento'): {2017},
    ('TONY', 'Cinco'): {2014},
    ('Takeo', 'Experience'): {2023},
    ('Takeo', 'Turismo'): {2008},
    ('Tuscani', 'Euphoria'): {2024},
    ('Tuscani', 'Euphoria M'): {2024},
    ('Tuscani', 'Rio Grande'): {2025},
    ('Tuscani', 'Rio Grande Electrified'): {2025},
    ('Viking', 'Blixt'): {2022},
    ('Viking', 'Daqing'): {2020},
    ('Viking', 'Ghent'): {2020},
    ('Viking', 'Gothenburg'): {2009},
    ('Viking', 'Kiruna'): {2023},
    ('Viking', 'Kompakt'): {2009},
    ('Viking', 'Obundet'): {2012},
    ('Viking', 'Stockholm'): {2021},
    ('Viking', 'Torslanda Sedan'): {1997, 2016, 2020},
    ('Viking', 'Torslanda Wagon'): {1997, 2016, 2020},
    ('Vision', 'Dominator'): {2006, 2024},
    ('Vision', 'Pioneer'): {2023},
    ('Vision', 'Prairie'): {2020},
    ('Vision', 'Prairie 2500HD'): {2020},
    ('Vision', 'Prima'): {2012, 2023},
    ('Vision', 'Prima Aqua-Cell'): {2023},
    ('Vision', 'Puremia'): {2016, 2025},
    ('Vision', 'Rainier'): {2017, 2019, 2023},
    ('Vision', 'Riptide'): {2024},
    ('Vision', 'Riptide Freedom'): {2023},
    ('Vision', 'Yosemite'): {2024},
    ('Volzhsky', 'Rocket'): {1995},
    ('WeGo', 'Coral'): {1990},
    ('Western', 'Cervid'): {1997},
    ('Western', 'Kobold'): {2023},
    ('Western', 'Leviathan'): {2025},
    ('Western', 'Mamba'): {1994, 2021},
    ('Western', 'Mamba Plus'): {1994},
    ('Western', 'Protogen'): {2022, 2026},
    ('Western', 'Protogen-X'): {2022, 2026},
    ('Western', 'Python'): {1997, 2021},
    ('Western', 'SYNTH'): {2022},
    ('Western', 'Sergal'): {2026},
    ('Western', 'Sergal Convertible'): {2026},
    ('Western', 'Wendigo'): {2002},
    ('Wolfsburg', 'Charge'): {1997, 2003, 2013},
    ('Wolfsburg', 'Classic'): {1965},
    ('Wolfsburg', 'Crouton'): {2009},
    ('Wolfsburg', 'Discovery'): {2022},
    ('Wolfsburg', 'Glide'): {2008},
    ('Wolfsburg', 'Glide Combi'): {2009},
    ('Wolfsburg', 'Handel'): {2012, 2014, 2018},
    ('Wolfsburg', 'Karen'): {2017},
    ('Wolfsburg', 'New Classic'): {2003, 2008, 2013},
    ('Wolfsburg', 'Pioneer'): {2023},
    ('Wolfsburg', 'Pitch'): {2000, 2013, 2016, 2019, 2022},
    ('Wolfsburg', 'Pitch Alltrack'): {2019},
    ('Wolfsburg', 'Pitch SportWagen'): {2016, 2019},
    ('Wolfsburg', 'Poseidon'): {2018, 2023},
    ('Wolfsburg', 'Poseidon Sportback'): {2023},
    ('Wolfsburg', 'Raven'): {2015},
    ('Wolfsburg', 'Sprint'): {2008},
    ('Wolfsburg', 'Symphony'): {2021},
    ('Wolfsburg', 'Tesuque'): {2022},
    ('Wolfsburg', 'Tijuana'): {2021},
    ('Wolfsburg', 'Tornado'): {2013, 2017},
    ('Wolfsburg', 'Van'): {1961},
    ('Wynne', 'Model-12'): {1983},
    ('Zephyr', 'Vicieux'): {2015},
}

RARITY_YEARS = {"common": (1995, 2026), "damaged": (1995, 2026), "rare": (2005, 2026), "legendary": (2015, 2026)}

# ── Trailers ───────────────────────────────────────────────

TRAILER_BRAND = "Durable"

TRAILER_COMMON = [
    ("4' x 6' Enclosed Box Trailer", 3500),
    ("6' x 8' Trailer", 4000),
    ("12' x 6' Enclosed Box Trailer", 5500),
    ("12' x 6' Off-Road Trailer", 6500),
    ("Boat Trailer", 5000),
    ("16' x 6' Enclosed Box Trailer", 7500),
    ("16' x 8' Car Transporter", 9000),
    ("15' x 8' Tear Drop Camper", 12000),
    ("10' x 6' Concrete Mixer", 10000),
    ("16' x 8' Camper", 15000),
    ("20' x 8' Dual Axle Camper", 22000),
    ("8' x 24' Car Transporter", 14000),
]

TRAILER_RARE = [
    ("Sign Message Trailer", 18000),
    ("Speed Readout Trailer", 20000),
]

TRAILER_DESCRIPTIONS = {
    "Enclosed": "Закрытый прицеп для перевозки грузов. Идеально подходит для хранения и транспортировки.",
    "Off-Road": "Внедорожный прицеп для тяжёлых условий эксплуатации.",
    "Car Transporter": "Автовоз для перевозки автомобилей. Незаменим для автосалонов и эвакуаторов.",
    "Camper": "Жилой прицеп-дача. Всё необходимое для комфортного отдыха на природе.",
    "Dual Axle Camper": "Большой жилой прицеп с двумя осями. Простор и комфорт для всей семьи!",
    "Tear Drop Camper": "Компактный жилой прицеп-капля. Лёгкий и экономичный.",
    "Trailer": "Универсальный открытый прицеп для перевозки любых грузов.",
    "Boat Trailer": "Прицеп для перевозки лодок и катеров.",
    "Concrete Mixer": "Прицеп-бетономешалка для строительных работ.",
    "Sign Message": "Информационный прицеп с электронным табло. Используется дорожными службами.",
    "Speed Readout": "Прицеп с радарным табло скорости. Помогает контролировать скорость на дорогах.",
}

TRAILER_TITLES = [
    "Грузовой транспорт",
    "Коммерческий прицеп",
    "Промышленный прицеп",
    "Прицеп специального назначения",
    "Прицеп для бизнеса",
]

TRAILER_CONDITIONS = [
    "Отличное техническое состояние", "В хорошем состоянии", "Без нареканий",
    "В идеальном состоянии", "Как новый", "Готов к эксплуатации",
]


def generate_trailer(target_rarity: str | None = None) -> dict:
    for _ in range(50):
        rarity = target_rarity if target_rarity else random.choices(
            ["common", "rare"], weights=[70, 30], k=1
        )[0]
        if rarity == "rare":
            model, base_price = random.choice(TRAILER_RARE)
        else:
            model, base_price = random.choice(TRAILER_COMMON)

        year = 2024 if rarity == "rare" else random.randint(2019, 2024)
        price_variance = random.randint(-2000, 3000)
        price = max(500, int(base_price + price_variance))
        miles = random.randint(500, 120000)

        desc_key = model.split("'")[-1].strip() if "'" in model else model
        for key, desc in TRAILER_DESCRIPTIONS.items():
            if key in model:
                description = desc
                break
        else:
            description = "Надёжный прицеп для решения любых задач."

        title = random.choice(TRAILER_TITLES)
        condition = random.choice(TRAILER_CONDITIONS)
        features = random.sample(list(TRAILER_DESCRIPTIONS.values()), k=random.randint(2, 4))
        rarity_label = "⭐ Редкий (Public Services)" if rarity == "rare" else ""
        full_desc = (
            f"{condition}. {' • '.join(features)}. {title}. {description}"
        )

        vin = "TR" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=15))
        license_plate = f"TRL-{random.randint(100, 999)}"
        return {
            "make": TRAILER_BRAND,
            "model": model,
            "year": year,
            "price": price,
            "miles": miles,
            "description": full_desc,
            "vin": vin,
            "license_plate": license_plate,
            "color": "",
            "rarity": rarity,
            "guid": f"trl_{rarity}_{vin}",
        }
    return generate_trailer()


def format_trailer_caption(trailer: dict, vehicle_id: int) -> str:
    rarity_line = "\n⭐ Редкий (Public Services)" if trailer["rarity"] == "rare" else ""
    return (
        f"🚛 <b>{trailer['year']} {trailer['make']} {trailer['model']}</b>\n"
        f"📍 Truck Planet, Greenville, WI\n"
        f"💰 ${trailer['price']:,} | {trailer['miles']:,} миль\n"
        f"🆔 Лот: <b>#{vehicle_id}</b>{rarity_line}"
    )


def get_real_brand(make: str) -> str | None:
    return BRAND_TO_REAL.get(make)


def get_car_title(make: str, model: str) -> str:
    if make in LICENSED_BRANDS:
        return f"{make} {model}"
    real = get_real_brand(make)
    if real and real != "Fictional":
        return f"{make} {model} ({real} {model})"
    return f"{make} {model}"


def pick_rarity() -> str:
    roll = random.randint(1, 100)
    cumulative = 0
    for rarity, weight in RARITY_WEIGHTS.items():
        cumulative += weight
        if roll <= cumulative:
            return rarity
    return "damaged"


def generate_car(target_rarity: str | None = None) -> dict | None:
    for _ in range(200):
        rarity = target_rarity if target_rarity else pick_rarity()
        if rarity == "legendary":
            pool = LEGENDARY_CARS
        elif rarity == "rare":
            pool = RARE_CARS
        elif rarity == "damaged":
            pool = COMMON_CARS[:15]
        else:
            pool = COMMON_CARS

        if rarity != "damaged" and random.random() < 0.05:
            make, model = random.choice(LICENSED_CARS)
        elif rarity in ("common", "damaged") and random.random() < 0.18:
            make, model = random.choice(WORK_VEHICLES)
        else:
            make, model = random.choice(pool)

        if not is_purchasable(make, model):
            continue

        valid_years = list(CAR_YEARS.get((make, model), {}))
        if valid_years:
            year = random.choice(valid_years)
        else:
            yr_lo, yr_hi = RARITY_YEARS[rarity]
            year = random.randint(yr_lo, yr_hi)
        miles = random.randint(1000, 250000)
        override = MODEL_PRICE_OVERRIDES.get((make, model))
        if override:
            variance = max(1000, int(override * 0.05))
            price = int((override + random.randint(-variance, variance)) * RARITY_MULTIPLIERS[rarity])
        else:
            pool = CAR_POOL.get((make, model), "mid")
            pool_base = POOL_BASE_PRICE[pool]
            year_factor = max(0.5, 1.0 + (year - 2000) * 0.02)
            base = int(pool_base * year_factor)
            variance = max(1000, int(base * 0.15))
            price = int((base + random.randint(-variance, variance)) * RARITY_MULTIPLIERS[rarity])
        price = max(100, min(price, 5000000))
        city = random.choice(WI_CITIES_RU)
        color = random.choice(COLORS)

        if rarity == "damaged":
            condition = random.choice(DAMAGED_CONDITIONS)
            features = random.sample(FEATURES, k=random.randint(0, 2))
            title = random.choice(DAMAGED_TITLES)
            desc = (
                f"{color.lower()} {make} {model} {year}, {miles:,} миль. {condition.capitalize()}, "
                f"{' • '.join(features) + ' • ' if features else ''}{title.capitalize()}."
            )
        else:
            condition = random.choice(CONDITIONS)
            features = random.sample(FEATURES, k=random.randint(3, 6))
            title = random.choice(TITLES)
            color_prefix = f"{color.lower()} " if rarity == "common" else ""
            desc = (
                f"{color_prefix}{make} {model} {year}, {miles:,} миль. {condition.capitalize()}, "
                f"{' • '.join(features)}. {title.capitalize()}."
            )

        vin = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=17))
        license_plate = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}-{random.randint(100,999)}"
        rent_price = max(100, int(price * random.uniform(0.005, 0.015)) // 100 * 100)
        return {
            "make": make, "model": model, "year": year, "miles": miles,
            "price": price, "city": city, "description": desc, "vin": vin,
            "license_plate": license_plate, "color": color, "rarity": rarity,
            "rent_price": rent_price,
            "guid": f"gen_{rarity}_{vin}",
        }
    return generate_car()





def format_caption(car: dict, vehicle_id: int) -> str:
    rarity_prefix = RARITY_NAMES[car["rarity"]]
    rarity_line = f"\n{rarity_prefix}" if rarity_prefix else ""
    rent_line = f"\n🔑 ${car.get('rent_price', 0):,}/день в аренду" if car.get("rent_price", 0) > 0 else ""
    title = get_car_title(car["make"], car["model"])
    real_brand = get_real_brand(car["make"])
    lines = [
        f"🚗 <b>{car['year']} {title}</b>",
        f"📍 {car['city']}, WI",
        f"💰 ${car['price']:,} | {car['miles']:,} миль{rent_line}",
        f"🎨 {car['color']}",
        f"🆔 Лот: <b>#{vehicle_id}</b>{rarity_line}",
    ]
    if car["make"] in LICENSED_BRANDS:
        lines.append("✅ Лицензионный дилер")
    if real_brand and real_brand != "Fictional":
        lines.append(f"📸 {real_brand} {car['model']} (фото для примера)")
    else:
        lines.append("📸 Фото для примера")
    return "\n".join(lines)


async def send_car(bot, chat_id: int, car: dict, message_thread_id: int | None = None) -> bool:
    if await is_listing_posted(car["guid"]):
        return False

    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"], chat_id, car.get("rent_price", 0),
    )
    caption = format_caption(car, vehicle_id)

    try:
        send_args = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        await bot.send_message(**send_args)

        await mark_listing_posted(car["guid"])
        return True
    except Exception as e:
        logger.error("Send error: %s", e)
        if "chat not found" in str(e).lower():
            logger.warning("Chat %s not found — disabling poster for this chat", chat_id)
            try:
                await set_config(f"poster_enabled:{chat_id}", "0")
            except Exception:
                pass
        return False


async def post_new_car(bot, chat_id: int, message_thread_id: int | None = None) -> bool:
    # Раз в день гарантированно редкая или легендарная тачка
    last_luxury_key = f"poster_luxury_post:{chat_id}"
    last_luxury_raw = await get_config(last_luxury_key)
    last_luxury = float(last_luxury_raw) if last_luxury_raw else 0.0
    force_luxury = (time.time() - last_luxury) > 86400

    for _ in range(50):
        if force_luxury:
            target_rarity = random.choices(["rare", "legendary"], weights=[20, 12])[0]
        else:
            target_rarity = None
        car = generate_car(target_rarity=target_rarity)
        if car is None:
            continue
        if await is_listing_posted(car["guid"]):
            continue
        if await is_model_recently_posted(car["make"], car["model"], hours=72):
            continue
        result = await send_car(bot, chat_id, car, message_thread_id)
        if result:
            await mark_model_posted(car["make"], car["model"])
            if force_luxury:
                await set_config(last_luxury_key, str(time.time()))
        return result
    return False


async def force_post_one(bot, chat_id: int, message_thread_id: int | None = None) -> str:
    car = generate_car()
    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"], chat_id, car.get("rent_price", 0),
    )
    caption = format_caption(car, vehicle_id)
    try:
        send_args = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        await bot.send_message(**send_args)

        await mark_listing_posted(car["guid"])
        await mark_model_posted(car["make"], car["model"])
        badge = RARITY_NAMES[car["rarity"]]
        title = get_car_title(car["make"], car["model"])
        return f"✅ #{vehicle_id} {car['year']} {title} — {car['city']} {badge}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


# ── House auto-poster ─────────────────────────────────────

HOUSE_PRICES_BASE = [65000, 145000, 120000, 165000, 110000, 200000, 350000, 195000, 480000,
                     150000, 135000, 250000, 155000, 380000, 210000, 175000, 40000, 185000,
                     170000, 195000, 160000, 165000, 190000, 180000, 230000, 200000, 220000,
                     20000, 25000, 30000, 35000]

HOUSE_FEATURES = [
    "камин", "бассейн", "гараж на 2 машины", "патио", "новая кухня",
    "новая кровля", "отремонтирован", "центральное кондиционирование",
    "тёплые полы", "система безопасности", "джакузи", "подвал",
    "мансарда", "терраса", "сад", "забор", "новая проводка",
    "видеодомофон", "кладовка", "прачечная",
]

HOUSE_CONDITIONS = [
    "отличное", "хорошее", "требует косметического ремонта",
    "после капитального ремонта", "новое покрытие",
]

HOUSE_PRICE_VARIANTS = {
    "отличное": 1.0, "хорошее": 0.9, "требует косметического ремонта": 0.7,
    "после капитального ремонта": 1.15, "новое покрытие": 1.05,
}


def generate_house() -> dict:
    # Weighted: cheaper houses appear more often than mansions
    _weights = [5, 3, 3, 3, 3, 2, 1, 3, 1, 3, 3, 2, 3,
                1, 2, 3, 5, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2,
                6, 6, 5, 4]
    ht_id = random.choices(range(1, 32), weights=_weights)[0]
    ht = None
    for h in [
        (1, "Mobile Home", 3, 2.5, 900, "Самый бюджетный вариант."),
        (2, "90's 2-Story House", 3, 2.5, 1600, "Двухэтажный дом. Бильярд на 2 этаже."),
        (3, "Average Suburban House", 3, 2.5, 1400, "Стандартный пригородный дом."),
        (4, "Modern Average Suburban House", 3, 2.5, 1700, "Современный пригородный дом."),
        (5, "Upper-Class 90's Bungalow", 2, 1.5, 1100, "Небольшое бунгало."),
        (6, "Average 2-Story House", 4, 3.5, 2200, "Двухэтажный дом в фермерском стиле."),
        (7, "Mansion #1", 5, 3.5, 4000, "Особняк!"),
        (8, "Old Farmhouse", 4, 2.5, 2500, "Старый фермерский дом с камином."),
        (9, "Lakeside Lodge", 4, 3.5, 3800, "Дом на озере с пирсом."),
        (10, "Average 2-Story Suburban House", 3, 3.0, 1800, "Пригородный двухэтажный дом."),
        (11, "Old Suburban House", 4, 4.0, 2000, "Старый пригородный дом."),
        (12, "Original 2-Story Suburban House", 3, 3.0, 1800, "Редчайший дом! Из бета-версии."),
        (13, "Average 2-Story Suburban House #3", 3, 2.5, 1700, "Пригородный двухэтажный дом."),
        (14, "Mansion #2", 4, 3.5, 4200, "Второй особняк."),
        (15, "Large 2-Story Suburban House", 3, 3.0, 2400, "Большой пригородный дом."),
        (16, "Average Suburban House", 5, 3.0, 2300, "Просторный пригородный дом."),
        (17, "Mobile Home", 1, 1.0, 500, "Маленький мобильный дом."),
        (18, "Modern Triangle House", 3, 2.0, 1600, "Современный треугольный дом."),
        (19, "Modern House", 3, 2.0, 1500, "Современный дом."),
        (20, "2-Story Modern House", 3, 2.5, 1900, "Двухэтажный современный дом."),
        (21, "Mid-Century Modern House", 3, 2.0, 1500, "Дом середины века."),
        (22, "Modern House", 3, 2.0, 1500, "Современный дом."),
        (23, "Cozy Rustic Suburban House", 3, 3.0, 2000, "Уютный деревенский дом."),
        (24, "Average Suburban Family House", 4, 3.0, 2200, "Средний семейный дом."),
        (25, "Large 2-Story House", 3, 3.0, 2500, "Большой двухэтажный дом."),
        (26, "2-Story Suburban House", 4, 3.0, 2300, "Двухэтажный пригородный дом."),
        (27, "2-Story Farm-Style House", 3, 3.0, 2400, "Двухэтажный фермерский дом."),
        (28, "Studio Apartment", 1, 1.0, 400, "Микро-студия. Самое дешёвое жильё."),
        (29, "Tiny House", 1, 1.0, 300, "Миниатюрный домик на колёсах."),
        (30, "Cabin", 2, 1.0, 700, "Небольшая деревенская хижина."),
        (31, "Small Ranch House", 2, 1.5, 1000, "Маленький ранчо с участком."),
    ]:
        if h[0] == ht_id:
            ht = h
            break

    nids = HOUSE_TYPE_NEIGHBORHOODS.get(ht_id, [0])
    nb_id = random.choice(nids) + 1
    nb_name = NEIGHBORHOODS[nb_id - 1]

    base_price = HOUSE_PRICES_BASE[ht_id - 1]
    condition = random.choice(HOUSE_CONDITIONS)
    mult = HOUSE_PRICE_VARIANTS[condition]
    price = int(base_price * mult * random.uniform(0.85, 1.15))
    price = max(10000, price // 1000 * 1000)

    rent_price = max(100, int(price * random.uniform(0.005, 0.015)) // 100 * 100)
    features = random.sample(HOUSE_FEATURES, k=random.randint(2, 5))
    desc = f"{ht[1]}. {' • '.join(features)}. Состояние: {condition}."

    guid = f"house_{ht_id}_{nb_id}_{random.randint(100000, 999999)}"

    return {
        "house_type_id": ht_id,
        "neighborhood_id": nb_id,
        "type_name": ht[1],
        "neighborhood": nb_name,
        "bedrooms": ht[2],
        "bathrooms": ht[3],
        "sqft": ht[4],
        "description": desc,
        "price": price,
        "rent_price": rent_price,
        "condition": condition,
        "guid": guid,
    }


def format_house_caption(house: dict, house_id: int) -> str:
    rent_line = f"🔑 ${house.get('rent_price', 0):,}/день в аренду\n" if house.get("rent_price", 0) > 0 else ""
    return (
        f"🏠 <b>{house['type_name']}</b>\n"
        f"📍 Район: <b>{house['neighborhood']}</b>\n"
        f"💰 ${house['price']:,}\n"
        f"{rent_line}"
        f"🛏 {house['bedrooms']} спальни | 🛁 {house['bathrooms']} ванны | 📐 {house['sqft']:,} кв.футов\n"
        f"📝 {house['description']}\n"
        f"🆔 Лот: <b>#{house_id}</b>"
    )


async def send_house(bot, chat_id: int, house: dict, message_thread_id: int | None = None) -> bool:
    if await is_listing_posted(house["guid"]):
        return False

    house_id = await create_house_listing(
        chat_id, house["house_type_id"], house["neighborhood_id"],
        house["price"], house["guid"], house.get("rent_price", 0),
    )
    caption = format_house_caption(house, house_id)

    try:
        send_args = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        await bot.send_message(**send_args)

        await mark_listing_posted(house["guid"])
        return True
    except Exception as e:
        logger.error("House send error: %s", e)
        if "chat not found" in str(e).lower() or "forbidden" in str(e).lower():
            try:
                await set_config(f"poster_houses_enabled:{chat_id}", "0")
            except Exception:
                pass
        return False


async def post_new_house(bot, chat_id: int, message_thread_id: int | None = None) -> bool:
    for _ in range(50):
        house = generate_house()
        if not await is_listing_posted(house["guid"]):
            return await send_house(bot, chat_id, house, message_thread_id)
    return False


async def force_post_house(bot, chat_id: int, message_thread_id: int | None = None) -> str:
    house = generate_house()
    house_id = await create_house_listing(
        chat_id, house["house_type_id"], house["neighborhood_id"],
        house["price"], house["guid"], house.get("rent_price", 0),
    )
    caption = format_house_caption(house, house_id)
    try:
        send_args = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        await bot.send_message(**send_args)
        await mark_listing_posted(house["guid"])
        return f"✅ #{house_id} {house['type_name']} — {house['neighborhood']}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


# ── Trailer auto-poster ──────────────────────────────────


async def send_trailer(bot, chat_id: int, trailer: dict, message_thread_id: int | None = None) -> bool:
    if await is_listing_posted(trailer["guid"]):
        return False

    vehicle_id = await create_trailer(
        trailer["make"], trailer["model"], trailer["year"], trailer["price"],
        trailer["miles"], trailer["description"], trailer["vin"], trailer["license_plate"],
        trailer["color"], trailer["rarity"], chat_id,
    )
    caption = format_trailer_caption(trailer, vehicle_id)

    try:
        send_args = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        await bot.send_message(**send_args)

        await mark_listing_posted(trailer["guid"])
        return True
    except Exception as e:
        logger.error("Trailer send error: %s", e)
        if "chat not found" in str(e).lower():
            try:
                await set_config(f"poster_enabled:{chat_id}", "0")
            except Exception:
                pass
        return False


async def post_new_trailer(bot, chat_id: int, message_thread_id: int | None = None) -> bool:
    for _ in range(50):
        trailer = generate_trailer()
        if trailer is None:
            continue
        if await is_listing_posted(trailer["guid"]):
            continue
        result = await send_trailer(bot, chat_id, trailer, message_thread_id)
        return result
    return False


async def force_post_trailer(bot, chat_id: int, message_thread_id: int | None = None) -> str:
    trailer = generate_trailer()
    vehicle_id = await create_trailer(
        trailer["make"], trailer["model"], trailer["year"], trailer["price"],
        trailer["miles"], trailer["description"], trailer["vin"], trailer["license_plate"],
        trailer["color"], trailer["rarity"], chat_id,
    )
    caption = format_trailer_caption(trailer, vehicle_id)
    try:
        send_args = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        if message_thread_id:
            send_args["message_thread_id"] = message_thread_id
        await bot.send_message(**send_args)

        await mark_listing_posted(trailer["guid"])
        return f"✅ #{vehicle_id} {trailer['year']} {trailer['make']} {trailer['model']}"
    except Exception as e:
        return f"❌ Ошибка: {e}"


async def auto_poster_loop(bot):
    logger.info("Auto-poster loop started (bot=%s)", type(bot).__name__)
    TICK = 15
    errors = 0
    counter = 0

    while True:
        try:
            counter += 1
            if counter % 40 == 0:
                logger.info("Auto-poster heartbeat (tick %s)", counter)
            if counter % 240 == 0:
                cleaned = await clean_old_model_posts(72)
                if cleaned:
                    logger.info("Cleaned %s old model post records", cleaned)

            all_config = await get_config("poster_chats") or ""
            chat_ids = [c for c in all_config.split(",") if c]
            logger.debug("Poster check: %s chats configured", len(chat_ids))

            for cid_str in chat_ids:
                chat_id = int(cid_str)

                # ── Cars ──
                car_enabled = await get_config(f"poster_enabled:{chat_id}")
                if car_enabled == "1":
                    interval_raw = await get_config(f"poster_interval:{chat_id}")
                    interval_min = int(interval_raw) if interval_raw and interval_raw.isdigit() else 120
                    target_raw = await get_config(f"poster_cars_channel:{chat_id}")
                    target = int(target_raw) if target_raw else chat_id
                    topic_raw = await get_config(f"poster_cars_topic:{chat_id}")
                    topic = int(topic_raw) if topic_raw else None

                    last_key = f"poster_last_post:{chat_id}"
                    last_raw = await get_config(last_key)
                    last_ts = float(last_raw) if last_raw else 0.0
                    now = time.time()
                    elapsed = now - last_ts
                    needed = interval_min * 60

                    if elapsed >= needed:
                        logger.info("Posting car for chat %s (interval=%s min)", chat_id, interval_min)
                        ok = await post_new_car(bot, target, topic)
                        await set_config(last_key, str(now))
                        if ok:
                            errors = 0
                        else:
                            logger.warning("Car post failed for chat %s", chat_id)

                # ── Houses ──
                house_enabled = await get_config(f"poster_houses_enabled:{chat_id}")
                if house_enabled == "1":
                    h_interval_raw = await get_config(f"poster_houses_interval:{chat_id}")
                    h_interval = int(h_interval_raw) if h_interval_raw and h_interval_raw.isdigit() else 180
                    h_target_raw = await get_config(f"poster_houses_channel:{chat_id}")
                    h_target = int(h_target_raw) if h_target_raw else chat_id
                    h_topic_raw = await get_config(f"poster_houses_topic:{chat_id}")
                    h_topic = int(h_topic_raw) if h_topic_raw else None

                    h_last_key = f"poster_houses_last:{chat_id}"
                    h_last_raw = await get_config(h_last_key)
                    h_last_ts = float(h_last_raw) if h_last_raw else 0.0
                    now = time.time()
                    h_elapsed = now - h_last_ts
                    h_needed = h_interval * 60

                    if h_elapsed >= h_needed:
                        logger.info("Posting house for chat %s (interval=%s min)", chat_id, h_interval)
                        ok = await post_new_house(bot, h_target, h_topic)
                        await set_config(h_last_key, str(now))
                        if ok:
                            errors = 0
                        else:
                            logger.warning("House post failed for chat %s", chat_id)

                # ── Trailers ──
                trailer_enabled = await get_config(f"poster_trailers_enabled:{chat_id}")
                if trailer_enabled == "1":
                    t_interval_raw = await get_config(f"poster_trailers_interval:{chat_id}")
                    t_interval = int(t_interval_raw) if t_interval_raw and t_interval_raw.isdigit() else 180
                    t_target_raw = await get_config(f"poster_trailers_channel:{chat_id}")
                    t_target = int(t_target_raw) if t_target_raw else chat_id
                    t_topic_raw = await get_config(f"poster_trailers_topic:{chat_id}")
                    t_topic = int(t_topic_raw) if t_topic_raw else None

                    t_last_key = f"poster_trailers_last:{chat_id}"
                    t_last_raw = await get_config(t_last_key)
                    t_last_ts = float(t_last_raw) if t_last_raw else 0.0
                    now = time.time()
                    t_elapsed = now - t_last_ts
                    t_needed = t_interval * 60

                    if t_elapsed >= t_needed:
                        logger.info("Posting trailer for chat %s (interval=%s min)", chat_id, t_interval)
                        ok = await post_new_trailer(bot, t_target, t_topic)
                        await set_config(t_last_key, str(now))
                        if ok:
                            errors = 0
                        else:
                            logger.warning("Trailer post failed for chat %s", chat_id)

            # ── Rent collection (every 4 ticks ≈ 1 min) ──
            if counter % 4 == 0:
                try:
                    rented = await get_all_rented_houses()
                    for h in rented:
                        result = await collect_rent(h["id"])
                        if result.get("action") == "collected":
                            logger.info("Rent collected for house %s: $%s", h["id"], result["price"])
                        elif result.get("action") == "evicted":
                            logger.info("Tenant evicted from house %s (missed %s days)", h["id"], result.get("missed"))
                        elif result.get("action") == "missed":
                            logger.debug("Rent missed for house %s (missed %s days)", h["id"], result.get("missed"))
                except Exception as e:
                    logger.error("Rent collection error: %s", e)
            # ── Car rent collection ──
            if counter % 4 == 0:
                try:
                    rc = await get_all_rented_cars()
                    for v in rc:
                        result = await collect_car_rent(v["id"])
                        if result.get("action") == "collected":
                            logger.info("Car rent collected for %s: $%s", v["id"], result["price"])
                        elif result.get("action") == "evicted":
                            logger.info("Tenant evicted from car %s (missed %s days)", v["id"], result.get("missed"))
                except Exception as e:
                    logger.error("Car rent collection error: %s", e)
        except Exception as e:
            logger.error("Auto-poster loop error: %s", e, exc_info=True)
            errors += 1
            if errors > 10:
                logger.critical("Too many poster errors, sleeping 5 min")
                await asyncio.sleep(300)
                errors = 0

        await asyncio.sleep(TICK)
