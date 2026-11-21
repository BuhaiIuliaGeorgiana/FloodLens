// Geoman extends the global `L` object, so Leaflet must be
// exposed globally before geoman is loaded
import L from "leaflet";

window.L = L;
