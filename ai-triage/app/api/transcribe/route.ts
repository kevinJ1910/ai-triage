import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const backendUrl = process.env.DJANGO_BACKEND_URL || 'http://localhost:8000';
    
    // Forward the multipart/form-data request to Django ASR backend
    const response = await fetch(`${backendUrl}/api/transcribe/`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: 'ASR backend error', details: errorText },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Transcription proxy error:', error);
    return NextResponse.json(
      { error: 'Transcription failed to reach backend', detail: error.message },
      { status: 502 }
    );
  }
}
