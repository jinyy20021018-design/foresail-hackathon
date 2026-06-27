export type MaritimeRoute = {
  distanceNauticalMiles: number;
  source: string;
  coordinates: Array<[number, number]>;
};

// Planned route generated from the Eurostat/ORNL global shipping-lane network.
// Coordinates are stored as Leaflet [latitude, longitude] pairs.
export const MARITIME_ROUTES: Record<string, MaritimeRoute> = {
  "shanghai-chittagong": {
    distanceNauticalMiles: 3724,
    source: "Global Shipping Lane Network",
    coordinates: [
      [31.2304, 121.4737], [31.51, 121.419], [31.259, 121.84], [31.062, 121.944],
      [30.932, 122.669], [30.35, 122.879], [29.624, 122.653], [28.58, 122.239],
      [27.8, 121.3], [26.977, 120.788], [26.079, 120.233], [25.237, 119.82],
      [24.449, 119.339], [23.583, 118.724], [22.931, 118.203], [21.923, 117.438],
      [20.601, 116.502], [19.666, 115.841], [17.57, 114.338], [15.728, 112.965],
      [12.524, 111.478], [11.608, 111.053], [10.173, 110.028], [8.319, 108.702],
      [1.341, 104.482], [1.249, 104.146], [1.171, 103.861], [1.1, 103.6],
      [2, 102], [2.586, 101.316], [3.2, 100.6], [4.085, 99.764],
      [5.812, 98.128], [14.549, 93.639], [20, 92], [21.799, 91.63],
      [22.238, 91.761], [22.3569, 91.7832],
    ],
  },
};

export function getMaritimeRoute(origin: string, destination: string) {
  const key = `${normalizePort(origin)}-${normalizePort(destination)}`;
  return MARITIME_ROUTES[key];
}

function normalizePort(port: string) {
  const value = port.trim().toLowerCase();
  if (value.includes("shanghai")) return "shanghai";
  if (value.includes("chittagong") || value.includes("chattogram")) return "chittagong";
  return value.replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
