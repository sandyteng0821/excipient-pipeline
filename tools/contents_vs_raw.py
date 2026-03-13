from pathlib import Path

contents = """Acacia
Acesulfame Potassium
Acetic Acid Glacial
Acetone
Acetyltributyl Citrate
Acetyltriethyl Citrate
Agar
Albumin
Alcohol
Alginic Acid
Aliphatic Polyesters
Alitame
Almond Oil
Alpha Tocopherol
Aluminum Hydroxide Adjuvant
Aluminum Oxide
Aluminum Phosphate Adjuvant
Aluminum Stearate
Ammonia Solution
Ammonium Alginate
Ascorbic Acid
Ascorbyl Palmitate
Aspartame
Attapulgite
Bentonite
Benzalkonium Chloride
Benzethonium Chloride
Benzoic Acid
Benzyl Alcohol
Benzyl Benzoate
Boric Acid
Bronopol
Butylated Hydroxyanisole
Butylated Hydroxytoluene
Butylparaben
Calcium Alginate
Calcium Carbonate
Calcium Phosphate Dibasic Anhydrous
Calcium Phosphate Dibasic Dihydrate
Calcium Phosphate Tribasic
Calcium Stearate
Calcium Sulfate
Canola Oil
Carbomer
Carbon Dioxide
Carboxymethylcellulose Calcium
Carboxymethylcellulose Sodium
Carrageenan
Castor Oil
Castor Oil Hydrogenated
Cellulose Microcrystalline
Cellulose Powdered
Cellulose Silicified Microcrystalline
Cellulose Acetate
Cellulose Acetate Phthalate
Ceratonia
Cetostearyl Alcohol
Cetrimide
Cetyl Alcohol
Cetylpyridinium Chloride
Chitosan
Chlorhexidine
Chlorobutanol
Chlorocresol
Chlorodifluoroethane (HCFC)
Chlorofluorocarbons (CFC)
Chloroxylenol
Cholesterol
Citric Acid Monohydrate
Colloidal Silicon Dioxide
Coloring Agents
Copovidone
Corn Oil
Cottonseed Oil
Cresol
Croscarmellose Sodium
Crospovidone
Cyclodextrins
Cyclomethicone
Denatonium Benzoate
Dextrates
Dextrin
Dextrose
Dibutyl Phthalate
Dibutyl Sebacate
Diethanolamine
Diethyl Phthalate
Difluoroethane (HFC)
Dimethicone
Dimethyl Ether
Dimethyl Phthalate
Dimethyl Sulfoxide
Dimethylacetamide
Disodium Edetate
Docusate Sodium
Edetic Acid
Erythorbic Acid
Erythritol
Ethyl Acetate
Ethyl Lactate
Ethyl Maltol
Ethyl Oleate
Ethyl Vanillin
Ethylcellulose
Ethylene Glycol Palmitostearate
Ethylene Vinyl Acetate
Ethylparaben
Fructose
Fumaric Acid
Gelatin
Glucose Liquid
Glycerin
Glyceryl Behenate
Glyceryl Monooleate
Glyceryl Monostearate
Glyceryl Palmitostearate
Glycofurol
Guar Gum
Hectorite
Heptafluoropropane (HFC)
Hexetidine
Hydrocarbons (HC)
Hydrochloric Acid
Hydroxyethyl Cellulose
Hydroxyethylmethyl Cellulose
Hydroxypropyl Cellulose
Hydroxypropyl Cellulose Low-substituted
Hydroxypropyl Starch
Hypromellose
Hypromellose Acetate Succinate
Hypromellose Phthalate
Imidurea
Inulin
Iron Oxides
Isomalt
Isopropyl Alcohol
Isopropyl Myristate
Isopropyl Palmitate
Kaolin
Lactic Acid
Lactitol
Lactose Anhydrous
Lactose Monohydrate
Lactose Spray-Dried
Lanolin
Lanolin Alcohols
Lanolin Hydrous
Lauric Acid
Lecithin
Leucine
Linoleic Acid
Macrogol 15 Hydroxystearate
Magnesium Aluminum Silicate
Magnesium Carbonate
Magnesium Oxide
Magnesium Silicate
Magnesium Stearate
Magnesium Trisilicate
Malic Acid
Maltitol
Maltitol Solution
Maltodextrin
Maltol
Maltose
Mannitol
Medium-chain Triglycerides
Meglumine
Menthol
Methylcellulose
Methylparaben
Mineral Oil
Mineral Oil Light
Mineral Oil and Lanolin Alcohols
Monoethanolamine
Monosodium Glutamate
Monothioglycerol
Myristic Acid
Neohesperidin Dihydrochalcone
Nitrogen
Nitrous Oxide
Octyldodecanol
Oleic Acid
Oleyl Alcohol
Olive Oil
Palmitic Acid
Paraffin
Peanut Oil
Pectin
Petrolatum
Petrolatum and Lanolin Alcohols
Phenol
Phenoxyethanol
Phenylethyl Alcohol
Phenylmercuric Acetate
Phenylmercuric Borate
Phenylmercuric Nitrate
Phosphoric Acid
Polacrilin Potassium
Poloxamer
Polycarbophil
Polydextrose
Polyethylene Glycol
Polyethylene Oxide
Polymethacrylates
Poly(methyl vinyl ether/maleic anhydride)
Polyoxyethylene Alkyl Ethers
Polyoxyethylene Castor Oil Derivatives
Polyoxyethylene Sorbitan Fatty Acid Esters
Polyoxyethylene Stearates
Polyvinyl Acetate Phthalate
Polyvinyl Alcohol
Potassium Alginate
Potassium Benzoate
Potassium Bicarbonate
Potassium Chloride
Potassium Citrate
Potassium Hydroxide
Potassium Metabisulfite
Potassium Sorbate
Povidone
Propionic Acid
Propyl Gallate
Propylene Carbonate
Propylene Glycol
Propylene Glycol Alginate
Propylparaben
2-Pyrrolidone
Raffinose
Saccharin
Saccharin Sodium
Saponite
Sesame Oil
Shellac
Simethicone
Sodium Acetate
Sodium Alginate
Sodium Ascorbate
Sodium Benzoate
Sodium Bicarbonate
Sodium Borate
Sodium Chloride
Sodium Citrate Dihydrate
Sodium Cyclamate
Sodium Hyaluronate
Sodium Hydroxide
Sodium Lactate
Sodium Lauryl Sulfate
Sodium Metabisulfite
Sodium Phosphate Dibasic
Sodium Phosphate Monobasic
Sodium Propionate
Sodium Starch Glycolate
Sodium Stearyl Fumarate
Sodium Sulfite
Sorbic Acid
Sorbitan Esters
Sorbitol
Soybean Oil
Starch
Starch Pregelatinized
Starch Sterilizable Maize
Stearic Acid
Stearyl Alcohol
Sucralose
Sucrose
Sugar Compressible
Sugar Confectioner's
Sugar Spheres
Sulfobutylether b-Cyclodextrin
Sulfuric Acid
Sunflower Oil
Suppository Bases Hard Fat
Talc
Tartaric Acid
Tetrafluoroethane (HFC)
Thaumatin
Thimerosal
Thymol
Titanium Dioxide
Tragacanth
Trehalose
Triacetin
Tributyl Citrate
Triethanolamine
Triethyl Citrate
Vanillin
Vegetable Oil Hydrogenated
Water
Wax Anionic Emulsifying
Wax Carnauba
Wax Cetyl Esters
Wax Microcrystalline
Wax Nonionic Emulsifying
Wax White
Wax Yellow
Xanthan Gum
Xylitol
Zein
Zinc Acetate
Zinc Stearate"""

book = [n.strip() for n in contents.strip().split('\n')]
raw_stems = {f.stem for f in Path('data/raw').glob('*.json')}

# normalize: 去空格、括號、連字符
import re
def normalize(s):
    return re.sub(r'[\s\-\(\)/\'.]', '', s)

missing = []
for name in book:
    if normalize(name) not in {normalize(s) for s in raw_stems}:
        missing.append(name)

print(f'書上共 {len(book)} 個，raw 缺少 {len(missing)} 個：')
for m in missing:
    print(f'  {m}')