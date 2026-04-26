import { useEffect, useState } from "react";

import { Offcanvas, Card, Badge, ListGroup } from "react-bootstrap";

import type { MarkerData, ServiceType } from "./MarkerData";

interface Props {
  marker: MarkerData | null;
  onHide: () => void;
  isMobile: boolean;
}

function getServiceLabel(type: ServiceType): string {
  switch (type) {
    case "body_composition":
      return "Bodycomposition";
    case "blood_test":
      return "Bluttest";
    case "bone_density":
      return "Knochendichte";
  }
}

function getServiceBadge(type: ServiceType) {
  switch (type) {
    case "body_composition":
      return (
        <Badge
          bg=""
          className="p-1 mb-2 text-uppercase badge-outline-primary"
          key={"body-comp-badge"}
        >
          Body Composition
        </Badge>
      );
    case "blood_test":
      return (
        <Badge
          bg=""
          className="p-1 mb-2 text-uppercase badge-outline-danger"
          key={"blood-test-bagde"}
        >
          Bluttest
        </Badge>
      );
    case "bone_density":
      return (
        <Badge
          bg=""
          className="p-1 mb-2 text-uppercase badge-outline-secondary"
          key={"bone-density-bagde"}
        >
          Knochendichte
        </Badge>
      );
    default:
      return (
        <Badge
          bg=""
          className="p-1 mb-2 text-uppercase badge-outline-secondary"
        >
          Unbekannt
        </Badge>
      );
  }
}

function OffcanvasLocation({ marker, onHide, isMobile }: Props) {
  const [cachedMarker, setCachedMarker] = useState<MarkerData | null>(null);

  useEffect(() => {
    if (marker) setCachedMarker(marker);
  }, [marker]);

  const displayMarker = marker ?? cachedMarker;

  return (
    <Offcanvas
      show={marker !== null}
      onHide={onHide}
      placement={isMobile ? "bottom" : "end"}
      style={
        isMobile ? { height: "auto", maxHeight: "70vh" } : { height: "100vh" }
      }
    >
      <Offcanvas.Header
        closeButton
        className="offcanvas-header-theme"
        data-bs-theme="dark"
      >
        <div>
          <Offcanvas.Title className="fw-bold">
            {displayMarker?.location_name}
          </Offcanvas.Title>
          {displayMarker?.services.map((service) =>
            getServiceBadge(service.type),
          )}
        </div>
      </Offcanvas.Header>
      <Offcanvas.Body>
        <div>
          <small className="text-muted text-uppercase fw-bold">Adresse</small>
          <p className="mt-1">
            {displayMarker?.address?.street} <br />
            {displayMarker?.address?.postal_code} {displayMarker?.address?.city}{" "}
            <br />
            <small className="text-muted">
              {displayMarker?.geocode[0]}
              {", "}
              {displayMarker?.geocode[1]}
            </small>
          </p>
        </div>
        <div className="mt-4">
          <small className="text-muted text-uppercase fw-bold">Kontakt</small>
          <ListGroup>
            {displayMarker?.contact_info?.phone ? (
              <ListGroup.Item className="d-flex justify-content-between">
                <span className="text-muted">Telefon</span>
                <a
                  className="link-underline link-underline-opacity-0"
                  href={`tel:${displayMarker?.contact_info?.phone}`}
                >
                  {displayMarker?.contact_info?.phone}
                </a>
              </ListGroup.Item>
            ) : null}
            {displayMarker?.contact_info?.email ? (
              <ListGroup.Item className="d-flex justify-content-between">
                <span className="text-muted">Email</span>
                <a
                  className="link-underline link-underline-opacity-0"
                  href={`mailto:${displayMarker.contact_info.email}`}
                >
                  {displayMarker.contact_info.email}
                </a>
              </ListGroup.Item>
            ) : null}
            {displayMarker?.contact_info?.website ? (
              <ListGroup.Item className="d-flex justify-content-between">
                <span className="text-muted">Webseite</span>
                <a
                  className="link-underline link-underline-opacity-0"
                  href={displayMarker.contact_info.website}
                >
                  Webseite aufrufen ↗
                </a>
              </ListGroup.Item>
            ) : null}
          </ListGroup>
        </div>
        <Card className="border-0 mt-4">
          <Card.Body className="px-0 align-items-center d-flex justify-content-between">
            <ListGroup variant="flush">
              <ListGroup.Item className="px-0 align-items-center d-flex justify-content-between">
                <small className="text-muted fw-semibold text-uppercase">
                  Selbstzahler möglich
                </small>
                <Badge
                  bg=""
                  className={`badge-outline-${displayMarker?.self_pay === true ? "success" : "danger"}`}
                >
                  {displayMarker?.self_pay ? "Ja" : "Nein"}
                </Badge>
              </ListGroup.Item>
              {displayMarker?.services.map((service) => (
                <ListGroup.Item
                  className="px-0 align-items-center d-flex justify-content-between"
                  key={service.type}
                >
                  <small className="text-muted fw-semibold text-uppercase">
                    Preis {getServiceLabel(service.type)}
                  </small>
                  <div>
                    {service.price_eur > 0.0 ? (
                      <>
                        {service.price_eur}{" "}
                        {displayMarker.address.country === "CH" ? "CHF" : "€"}
                      </>
                    ) : (
                      "Keine Angabe"
                    )}
                  </div>
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Card.Body>
        </Card>
      </Offcanvas.Body>
    </Offcanvas>
  );
}

export default OffcanvasLocation;
