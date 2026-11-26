import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";

import "../lib/leafletGeoman";
import "leaflet/dist/leaflet.css";

// Initial view: the whole of Romania
const ROMANIA_CENTER = [45.9, 24.9];

// Adds the polygon drawing tools to the map and keeps a single zone.
// Calls onChange with a GeoJSON Polygon, or null when the zone is removed.
function DrawControls({ onChange }){
    const map = useMap();
    const currentLayer = useRef(null);
    const onChangeRef = useRef(onChange);

    useEffect(() => {
        onChangeRef.current = onChange;
    }, [onChange]);

    useEffect(() => {
        map.pm.addControls({
            position: "topleft",
            drawPolygon: true,
            drawRectangle: true,
            drawMarker: false,
            drawCircleMarker: false,
            drawPolyline: false,
            drawCircle: false,
            drawText: false,
            cutPolygon: false,
            rotateMode: false,
            editMode: true,
            dragMode: true,
            removalMode: true,
        });

        map.pm.setGlobalOptions({ allowSelfIntersection: false });

        function emit(layer){
            onChangeRef.current(layer ? layer.toGeoJSON().geometry : null);
        }

        function handleCreate(e){
            // Only one zone per event: drawing a new one replaces the old one
            if(currentLayer.current){
                currentLayer.current.remove();
            }

            currentLayer.current = e.layer;

            e.layer.on("pm:edit", () => emit(e.layer));
            e.layer.on("pm:dragend", () => emit(e.layer));

            emit(e.layer);
        }

        function handleRemove(e){
            if(e.layer === currentLayer.current){
                currentLayer.current = null;
                emit(null);
            }
        }

        map.on("pm:create", handleCreate);
        map.on("pm:remove", handleRemove);

        return () => {
            map.off("pm:create", handleCreate);
            map.off("pm:remove", handleRemove);
            map.pm.removeControls();
        };
    }, [map]);

    return null;
}

// Smoothly moves the map to the given bounds whenever they change.
// Leaflet picks the flight duration from the distance, so short hops stay short.
function FlyTo({ bounds }){
    const map = useMap();

    useEffect(() => {
        if(bounds){
            map.stop();
            map.flyToBounds(bounds, { maxZoom: 13, padding: [24, 24], easeLinearity: 0.2 });
        }
    }, [map, bounds]);

    return null;
}

function AoiDrawMap({ onChange, focus }){
    return(
        <MapContainer
            center={ROMANIA_CENTER}
            zoom={7}
            style={{height: "450px", width: "100%"}}
        >
            <TileLayer
                attribution='&copy; OpenStreetMap contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <DrawControls onChange={onChange}/>
            <FlyTo bounds={focus}/>
        </MapContainer>
    );
}

export default AoiDrawMap;
