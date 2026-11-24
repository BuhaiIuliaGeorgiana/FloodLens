export function safeReturnPath(value) {
    return typeof value==="string" && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/dashboard";
}
