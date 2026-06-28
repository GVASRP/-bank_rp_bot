import asyncio
import logging
import random
import time

from database import (
    is_listing_posted, mark_listing_posted, get_config, set_config, create_vehicle,
    create_house_listing, get_house_type, get_all_house_types, get_all_neighborhoods,
    get_neighborhood, HOUSE_TYPE_NEIGHBORHOODS, NEIGHBORHOODS,
    is_model_recently_posted, mark_model_posted, clean_old_model_posts,
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
]

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

RARITY_WEIGHTS = {"common": 70, "damaged": 10, "rare": 14, "legendary": 6}
RARITY_MULTIPLIERS = {"common": 1.0, "damaged": 0.25, "rare": 2.5, "legendary": 8.0}
RARITY_NAMES = {"common": "", "damaged": "💥 Битый", "rare": "⭐ Редкий", "legendary": "🔥🔥🔥 МЕГА-КАР 🔥🔥🔥"}
RARITY_YEARS = {"common": (1995, 2025), "damaged": (2005, 2018), "rare": (2015, 2025), "legendary": (2020, 2025)}


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


def generate_car() -> dict:
    for _ in range(200):
        rarity = pick_rarity()
        if rarity == "legendary":
            pool = LEGENDARY_CARS
        elif rarity == "rare":
            pool = RARE_CARS
        elif rarity == "damaged":
            pool = COMMON_CARS[:15]
        else:
            pool = COMMON_CARS

        if rarity != "damaged" and random.random() < 0.10:
            make, model = random.choice(LICENSED_CARS)
        else:
            make, model = random.choice(pool)

        if not is_purchasable(make, model):
            continue

        yr_lo, yr_hi = RARITY_YEARS[rarity]
        year = random.randint(yr_lo, yr_hi)
        miles = random.randint(1000, 250000)
        base_prices = {1995: 400, 1996: 500, 1997: 600, 1998: 800, 1999: 1000,
                       2000: 1200, 2001: 1500, 2002: 2000, 2003: 2500, 2004: 3000,
                       2005: 3500, 2006: 4000, 2007: 4500, 2008: 5000, 2009: 5500,
                       2010: 6000, 2011: 7000, 2012: 8000, 2013: 9000,
                       2014: 10000, 2015: 12000, 2016: 14000, 2017: 16000,
                       2018: 18000, 2019: 20000, 2020: 23000, 2021: 27000,
                       2022: 31000, 2023: 36000, 2024: 42000, 2025: 48000}
        brand_mult = REAL_BRAND_VALUE.get(make, 1.0)
        price = int((base_prices.get(year, 10000) + random.randint(-4000, 8000)) * RARITY_MULTIPLIERS[rarity] * brand_mult)
        price = max(100, price)
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
        return {
            "make": make, "model": model, "year": year, "miles": miles,
            "price": price, "city": city, "description": desc, "vin": vin,
            "license_plate": license_plate, "color": color, "rarity": rarity,
            "guid": f"gen_{rarity}_{vin}",
        }
    return generate_car()





def format_caption(car: dict, vehicle_id: int) -> str:
    rarity_prefix = RARITY_NAMES[car["rarity"]]
    rarity_line = f"\n{rarity_prefix}" if rarity_prefix else ""
    title = get_car_title(car["make"], car["model"])
    real_brand = get_real_brand(car["make"])
    lines = [
        f"🚗 <b>{car['year']} {title}</b>",
        f"📍 {car['city']}, WI",
        f"💰 ${car['price']:,} | {car['miles']:,} миль",
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
        car["color"], car["rarity"], chat_id,
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
    for _ in range(50):
        car = generate_car()
        if await is_listing_posted(car["guid"]):
            continue
        if await is_model_recently_posted(car["make"], car["model"]):
            continue
        result = await send_car(bot, chat_id, car, message_thread_id)
        if result:
            await mark_model_posted(car["make"], car["model"])
        return result
    return False


async def force_post_one(bot, chat_id: int, message_thread_id: int | None = None) -> str:
    car = generate_car()
    vehicle_id = await create_vehicle(
        car["make"], car["model"], car["year"], car["price"],
        car["miles"], car["city"], car["vin"], car["license_plate"],
        car["color"], car["rarity"], chat_id,
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
                     170000, 195000, 160000, 165000, 190000, 180000, 230000, 200000, 220000]

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
    ht_id = random.choice(list(range(1, 28)))
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
        "condition": condition,
        "guid": guid,
    }


def format_house_caption(house: dict, house_id: int) -> str:
    return (
        f"🏠 <b>{house['type_name']}</b>\n"
        f"📍 Район: <b>{house['neighborhood']}</b>\n"
        f"💰 ${house['price']:,}\n"
        f"🛏 {house['bedrooms']} спальни | 🛁 {house['bathrooms']} ванны | 📐 {house['sqft']:,} кв.футов\n"
        f"📝 {house['description']}\n"
        f"🆔 Лот: <b>#{house_id}</b>"
    )


async def send_house(bot, chat_id: int, house: dict, message_thread_id: int | None = None) -> bool:
    if await is_listing_posted(house["guid"]):
        return False

    house_id = await create_house_listing(
        chat_id, house["house_type_id"], house["neighborhood_id"],
        house["price"], house["guid"],
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
        if "chat not found" in str(e).lower():
            try:
                await set_config(f"poster_enabled:{chat_id}", "0")
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
        house["price"], house["guid"],
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
        except Exception as e:
            logger.error("Auto-poster loop error: %s", e, exc_info=True)
            errors += 1
            if errors > 10:
                logger.critical("Too many poster errors, sleeping 5 min")
                await asyncio.sleep(300)
                errors = 0

        await asyncio.sleep(TICK)
