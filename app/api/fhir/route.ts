import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const payload = await req.json();
    // Simulamos un retraso de red
    await new Promise(resolve => setTimeout(resolve, 800));
    
    // Retornamos 201 Created simulando un servidor FHIR (ej. HAPI FHIR)
    return NextResponse.json({ 
        message: "Resource created", 
        id: "fhir-enc-" + Math.floor(Math.random() * 1000000),
        resourceReceived: payload
    }, { status: 201 });
  } catch (error) {
    return NextResponse.json({ error: "Invalid FHIR payload" }, { status: 400 });
  }
}
