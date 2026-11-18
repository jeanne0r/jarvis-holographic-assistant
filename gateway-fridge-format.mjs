// Pure legacy display functions; no storage, network or equipment effects.
const FRIDGE_LOCATIONS = {
  frigo_cuisine: {
    id: "frigo_cuisine",
    name: "Frigo cuisine",
    sensor: "sensor.frigo_cuisine_stock",
    icon: "mdi:fridge",
    sourceUrl: "https://192.0.2.16:8788/frigo.html?location=frigo_cuisine",
  },
  frigo_dehors: {
    id: "frigo_dehors",
    name: "Frigo dehors",
    sensor: "sensor.frigo_dehors_stock",
    icon: "mdi:fridge-outline",
    sourceUrl: "https://192.0.2.16:8788/frigo.html?location=frigo_dehors",
  },
};

function normalizeFridgeLocation(value) {
  return FRIDGE_LOCATIONS[value] ? value : "frigo_cuisine";
}

function fridgeActiveItems(store, location = "") {
  const normalized = location ? normalizeFridgeLocation(location) : "";
  return store.items.filter((item) => {
    if (item.status !== "in_fridge") return false;
    const itemLocation = normalizeFridgeLocation(item.location || "frigo_cuisine");
    return !normalized || itemLocation === normalized;
  });
}

function fridgeSummary(store, location = "") {
  const active = fridgeActiveItems(store, location);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const soonLimit = new Date(today);
  soonLimit.setDate(today.getDate() + 3);
  const soon = active
    .filter((item) => item.expiresAt)
    .filter((item) => {
      const date = new Date(`${item.expiresAt}T12:00:00`);
      return !Number.isNaN(date.getTime()) && date <= soonLimit;
    })
    .sort((a, b) => String(a.expiresAt).localeCompare(String(b.expiresAt)));

  return {
    activeCount: active.length,
    soonCount: soon.length,
    expiredCount: soon.filter((item) => new Date(`${item.expiresAt}T12:00:00`) < today).length,
    soon: soon.slice(0, 8),
    location: location ? normalizeFridgeLocation(location) : "",
    updatedAt: new Date().toISOString(),
  };
}


export function fridgeView(store,parameters={}){
 const location=normalizeFridgeLocation(parameters.location||'frigo_cuisine');
 return {items:fridgeActiveItems(store,location).sort((a,b)=>String(a.expiresAt||'9999-12-31').localeCompare(String(b.expiresAt||'9999-12-31'))),summary:fridgeSummary(store,location),location:FRIDGE_LOCATIONS[location],locations:Object.values(FRIDGE_LOCATIONS),recentEvents:store.events.filter(e=>normalizeFridgeLocation(e.location||'frigo_cuisine')===location).slice(-20).reverse()};
}
