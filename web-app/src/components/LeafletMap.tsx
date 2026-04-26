import "leaflet/dist/leaflet.css";
import type { MarkerData } from "./MarkerData";

import markerBlue from "../assets/marker-blue.png";
import markerRed from "../assets/marker-red.png";
import markerBoth from "../assets/marker-both.png";

import { MapContainer, TileLayer, Marker } from "react-leaflet";
import { Icon, divIcon, point, type LatLngExpression } from "leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";

interface Props {
  markers: MarkerData[];
  onMarkerClick: (marker: MarkerData) => void;
  markerFilter: "dexa" | "blood" | "all";
}

const position: LatLngExpression = [51.1657, 10.4515];

const createCustomClusterIcon =
  (color: "red" | "blue" | "both") => (cluster: any) => {
    return divIcon({
      html: `<div class="cluster-icon cluster-color-${color}">${cluster.getChildCount()}</div>`,
      className: "custom-marker-cluster",
      iconSize: point(33, 33, true),
    });
  };

const customIconRed = new Icon({
  iconUrl: markerRed,
  iconSize: [35, 35],
});

const customIconBlue = new Icon({
  iconUrl: markerBlue,
  iconSize: [35, 35],
});

const customIconBoth = new Icon({
  iconUrl: markerBoth,
  iconSize: [35, 35],
});

function getMarkerClass(services: string[]): string {
  if (services.includes("blood_test")) {
    if (
      services.includes("body_composition") ||
      services.includes("bone_density")
    ) {
      return "both";
    } else return "blood";
  } else return "dexa";
}

function LeafletMap({ markers, onMarkerClick, markerFilter }: Props) {
  return (
    <MapContainer center={position} zoom={6}>
      <TileLayer
        attribution="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {markerFilter !== "dexa" ? (
        <MarkerClusterGroup
          chunkedLoading
          iconCreateFunction={createCustomClusterIcon("red")}
        >
          {markers.map((marker, index) =>
            getMarkerClass(marker.services.map((service) => service.type)) ==
            "blood" ? (
              <Marker
                key={marker.id || `${marker.location_name}-${index}`}
                position={marker.geocode}
                icon={customIconRed}
                eventHandlers={{ click: () => onMarkerClick(marker) }}
              ></Marker>
            ) : null,
          )}
        </MarkerClusterGroup>
      ) : null}

      {markerFilter !== "blood" ? (
        <MarkerClusterGroup
          chunkedLoading
          iconCreateFunction={createCustomClusterIcon("blue")}
        >
          {markers.map((marker, index) =>
            getMarkerClass(marker.services.map((service) => service.type)) ==
            "dexa" ? (
              <Marker
                key={marker.id || `${marker.location_name}-${index}`}
                position={marker.geocode}
                icon={customIconBlue}
                eventHandlers={{ click: () => onMarkerClick(marker) }}
              ></Marker>
            ) : null,
          )}
        </MarkerClusterGroup>
      ) : null}
      <MarkerClusterGroup
        chunkedLoading
        iconCreateFunction={createCustomClusterIcon("both")}
      >
        {markers.map((marker, index) =>
          getMarkerClass(marker.services.map((service) => service.type)) ==
          "both" ? (
            <Marker
              key={marker.id || `${marker.location_name}-${index}`}
              position={marker.geocode}
              icon={customIconBoth}
              eventHandlers={{ click: () => onMarkerClick(marker) }}
            ></Marker>
          ) : null,
        )}
      </MarkerClusterGroup>
    </MapContainer>
  );
}

export default LeafletMap;
