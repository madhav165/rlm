import { readFile } from 'fs/promises';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url);
    const path = url.searchParams.get('path');
    
    if (!path) {
      return NextResponse.json({ error: 'No path provided' }, { status: 400 });
    }
    
    // Security: Only allow reading from specific directories
    const allowedDirs = [
      process.cwd(),
      process.cwd() + '/public/logs',
    ];
    
    const resolvedPath = path.startsWith('/') ? path : process.cwd() + '/' + path;
    
    // Basic security check
    if (!allowedDirs.some(dir => resolvedPath.startsWith(dir))) {
      return NextResponse.json({ error: 'Access denied' }, { status: 403 });
    }
    
    const content = await readFile(resolvedPath, 'utf-8');
    return NextResponse.json({ content });
  } catch (error) {
    console.error('Error reading file:', error);
    return NextResponse.json({ error: 'Failed to read file' }, { status: 500 });
  }
}