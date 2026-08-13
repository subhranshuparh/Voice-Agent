import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import util from 'util';

const execAsync = util.promisify(exec);

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status') || 'all';

    const backendPath = path.resolve(process.cwd(), '../backend/src');
    const pyScript = `import sys, json; sys.path.append(r'${backendPath}'); import db; print(json.dumps(db.get_all_escalations('${status}')))`;

    const { stdout } = await execAsync(`python -c "${pyScript}"`);
    const escalations = JSON.parse(stdout.trim() || '[]');

    return NextResponse.json({ escalations });
  } catch (error: unknown) {
    const err = error as Error;
    console.error('Error in escalation endpoint:', err);
    return NextResponse.json(
      { error: 'Escalation operation failed', details: err.message },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { escalation_id, new_status } = body;

    if (!escalation_id || !new_status) {
      return NextResponse.json({ error: 'Missing escalation_id or new_status' }, { status: 400 });
    }

    const backendPath = path.resolve(process.cwd(), '../backend/src');
    const pyScript = `import sys, json; sys.path.append(r'${backendPath}'); import db; res = db.update_escalation_status('${escalation_id}', '${new_status}'); print(json.dumps({'success': res}))`;

    const { stdout } = await execAsync(`python -c "${pyScript}"`);
    const result = JSON.parse(stdout.trim() || '{"success": false}');

    return NextResponse.json(result);
  } catch (error: unknown) {
    const err = error as Error;
    console.error('Error updating escalation status:', err);
    return NextResponse.json(
      { error: 'Failed to update escalation status', details: err.message },
      { status: 500 }
    );
  }
}
