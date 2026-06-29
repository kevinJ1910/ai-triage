import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const backendUrl = process.env.DJANGO_BACKEND_URL || 'http://localhost:8000';
    
    // Forward the session reset request to Django ASR backend
    const response = await fetch(`${backendUrl}/api/transcribe/reset/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: 'ASR reset backend error', details: errorText },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Reset proxy error:', error);
    return NextResponse.json(
      { error: 'Reset failed to reach backend', detail: error.message },
      { status: 502 }
    );
  }
}
