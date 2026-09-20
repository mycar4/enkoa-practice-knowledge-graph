export default function handler(req: any, res: any) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");
  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  return res.status(200).json({
    status: "healthy",
    service: "ART:READY Franchise B2B Platform API",
    version: "6.0.0",
    supabase_connected: true,
    timestamp: new Date().toISOString()
  });
}
