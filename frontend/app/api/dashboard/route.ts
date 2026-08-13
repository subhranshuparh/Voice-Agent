import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import util from 'util';

const execAsync = util.promisify(exec);

export async function GET() {
  try {
    const backendPath = path.resolve(process.cwd(), '../backend/src');
    const pyScript = `import sys, json; sys.path.append(r'${backendPath}'); import db; print(json.dumps(db.get_call_analytics()))`;

    const { stdout } = await execAsync(`python -c "${pyScript}"`);
    const analytics = JSON.parse(stdout.trim() || '{}');

    return NextResponse.json(analytics);
  } catch (error: unknown) {
    const err = error as Error;
    console.error('Error fetching call analytics:', err);
    return NextResponse.json(
      { error: 'Failed to fetch call analytics', details: err.message },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const {
      status = 'successful',
      primary_action = 'PHC Lookup',
      failure_category,
      channel = 'browser',
    } = body;

    const backendPath = path.resolve(process.cwd(), '../backend/src');
    const failCatArg = failure_category ? `'${failure_category}'` : 'None';
    const pyScript = `import sys, json; sys.path.append(r'${backendPath}'); import db; print(json.dumps(db.record_test_call(status='${status}', primary_action='${primary_action}', failure_category=${failCatArg}, channel='${channel}')))`;

    const { stdout } = await execAsync(`python -c "${pyScript}"`);
    const result = JSON.parse(stdout.trim() || '{}');

    return NextResponse.json(result);
  } catch (error: unknown) {
    const err = error as Error;
    console.error('Error recording test call:', err);
    return NextResponse.json(
      { error: 'Failed to record test call', details: err.message },
      { status: 500 }
    );
  }
}
