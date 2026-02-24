import { readdir } from 'fs/promises';
import { join } from 'path';
import { NextResponse } from 'next/server';

const LOGS_DIR = join(process.cwd(), 'public', 'logs');

export async function GET() {
  try {
    const files = await readdir(LOGS_DIR);
    const jsonlFiles = files.filter(file => file.endsWith('.jsonl'));
    
    return NextResponse.json({ files: jsonlFiles });
  } catch (error) {
    console.error('Error reading logs directory:', error);
    return NextResponse.json({ files: [] }, { status: 500 });
  }
}