export type ServiceType = "body_composition" | "blood_test" | "bone_density";

export interface Service {
  type: ServiceType;
  price_eur: number;
}

export interface Address {
  street: string;
  postal_code: string;
  city: string;
  country: string;
}

export interface ContactInfo {
  phone?: string;
  email?: string;
  website?: string;
}

export interface MarkerData {
  id: number | string;
  geocode: [number, number];
  location_name: string;
  address: Address;
  contact_info: ContactInfo;
  self_pay: boolean;
  services: Service[];
}
