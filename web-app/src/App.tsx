import { useState, useEffect } from "react";
import { Container, Nav, Navbar, NavDropdown } from "react-bootstrap";

import LeafletMap from "./components/LeafletMap";
import OffcanvasLocation from "./components/OffcanvasLocation";
import type { MarkerData } from "./components/MarkerData";

import "leaflet/dist/leaflet.css";
import "./App.css";

async function getMarkerData(): Promise<MarkerData[]> {
  const response = await fetch("/api/providers", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const data = await response.json();

  return data.map((provider: any) => ({
    id: provider.id,
    geocode: [provider.latitude, provider.longitude] as [number, number],
    location_name: provider.name,
    address: {
      street: provider.street,
      postal_code: provider.postal_code,
      city: provider.city,
      country: provider.country,
    },
    contact_info: {
      phone: provider.phone,
      email: provider.email,
      website: provider.website,
    },
    self_pay: provider.self_pay,
    services: provider.services.map((service: any) => ({
      type: service.type,
      price_eur: service.price_eur,
    })),
  }));
}

function App() {
  const [markers, setMarkers] = useState<MarkerData[]>([]);
  const [selectedMarker, setSelectedMarker] = useState<MarkerData | null>(null);
  const [markerFilter, setMarkerFilter] = useState<"dexa" | "blood" | "all">(
    "all",
  );
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    getMarkerData().then(setMarkers);
  }, []);

  return (
    <>
      <div className="app-layout">
        <Navbar className="bg-white border-bottom py-2">
          <Container
            fluid
            className="px-4 d-flex justify-content-start align-items-center"
          >
            <Navbar.Brand className="fw-bolder m-0 p-0">
              Laborsuche DACH
            </Navbar.Brand>
            <Nav>
              <NavDropdown
                title="Filter"
                id="collapsible-nav-dropdown"
                className="ms-3 pt-1"
              >
                <NavDropdown.Item onClick={() => setMarkerFilter("dexa")}>
                  DEXA-Scan
                </NavDropdown.Item>
                <NavDropdown.Item onClick={() => setMarkerFilter("blood")}>
                  Blutlabor
                </NavDropdown.Item>
                <NavDropdown.Item onClick={() => setMarkerFilter("all")}>
                  Alle
                </NavDropdown.Item>
              </NavDropdown>
            </Nav>
          </Container>
        </Navbar>
        <div className="card map-container">
          <LeafletMap
            markers={markers}
            onMarkerClick={(marker) => setSelectedMarker(marker)}
            markerFilter={markerFilter}
          ></LeafletMap>
        </div>
      </div>
      <OffcanvasLocation
        marker={selectedMarker}
        onHide={() => setSelectedMarker(null)}
        isMobile={isMobile}
      />
    </>
  );
}

export default App;
