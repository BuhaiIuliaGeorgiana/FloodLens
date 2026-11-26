// Cautare fara diacritice si fara majuscule: "iasi" gaseste "Iași"
export const normalize = (text) => text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().trim();

// "Lupele (com. Pechea)" -> { name: "Lupele", commune: "Pechea" }
export function splitLocality(label){
    const match = label.match(/^(.*) \(com\. (.*)\)$/);
    return match ? { name: match[1], commune: match[2] } : { name: label, commune: null };
}

// Gaseste judetul si localitatea din lista noastra pentru o adresa Nominatim.
// places: { judet: [localitati] }; address: obiectul "address" din raspunsul reverse.
export function matchAddress(places, address){
    const countyName = address["ISO3166-2-lvl4"] === "RO-B" ? "București" : address.county?.replace(/^Județul /, "");
    const county = countyName && Object.keys(places).find((name) => normalize(name) === normalize(countyName));

    if(!county){
        return { county: null, locality: null };
    }

    const commune = address.municipality && normalize(address.municipality);
    const candidates = [address.city_district, address.village, address.town, address.city, address.municipality]
        .filter(Boolean).map(normalize);

    for(const candidate of candidates){
        const matches = places[county].filter((label) => normalize(splitLocality(label).name) === candidate);
        const best = matches.find((label) => normalize(splitLocality(label).commune ?? splitLocality(label).name) === commune) ?? matches[0];

        if(best){
            return { county, locality: best };
        }
    }

    return { county, locality: null };
}
