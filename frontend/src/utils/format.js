export function formatDay(value) {
    return new Date(value).toLocaleDateString("ro-RO", {timeZone:"Europe/Bucharest",day:"numeric",month:"short",year:"numeric"});
}
