/**
 * WhatsApp sender daemon — Baileys (no browser)
 *
 * Polls the Django OutgoingMessage SQLite table every POLL_INTERVAL ms.
 * Sends text and media (video/image) messages to WhatsApp groups.
 *
 * Usage:
 *   node sender.js [--db ../db.sqlite3] [--auth ./auth_state] [--poll 3000]
 */

import {
    makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import qrcode from 'qrcode-terminal';
import pino from 'pino';

// ── Config ────────────────────────────────────────────────────────────────────
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const args = process.argv.slice(2);
function getArg(name, fallback) {
    const idx = args.indexOf(name);
    return idx !== -1 ? args[idx + 1] : fallback;
}

const DB_PATH    = path.resolve(__dirname, getArg('--db',   '../db.sqlite3'));
const AUTH_DIR   = path.resolve(__dirname, getArg('--auth', './auth_state'));
const POLL_MS    = parseInt(getArg('--poll', '3000'), 10);
const MAX_RETRY  = 3;

// Docker container maps project root → /app
// Translate /app/... paths to actual host paths so Node.js can read media files
const APP_ROOT   = path.resolve(__dirname, '..');  // wa_sender/../ = project root

function resolveMediaPath(p) {
    if (!p) return p;
    if (p.startsWith('/app/')) return path.join(APP_ROOT, p.slice(5));
    return p;
}

const logger = pino({ level: 'info' });

// ── DB helpers ────────────────────────────────────────────────────────────────
const TABLE = 'whatsapp_monitor_outgoingmessage';

function openDb() {
    const db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    return db;
}

function fetchNextPending(db) {
    const now = new Date().toISOString();
    // Claim atomically: PENDING → SENDING
    const row = db.prepare(`
        SELECT * FROM ${TABLE}
        WHERE status = 'pending'
          AND (send_after IS NULL OR send_after <= ?)
        ORDER BY created_at
        LIMIT 1
    `).get(now);

    if (!row) return null;

    db.prepare(`UPDATE ${TABLE} SET status='sending' WHERE id=?`).run(row.id);
    return row;
}

function markSent(db, id) {
    db.prepare(`
        UPDATE ${TABLE} SET status='sent', sent_at=?, error='' WHERE id=?
    `).run(new Date().toISOString(), id);
}

function markFailed(db, id, err, retryCount) {
    const status = retryCount >= MAX_RETRY ? 'failed' : 'pending';
    db.prepare(`
        UPDATE ${TABLE} SET status=?, error=?, retry_count=? WHERE id=?
    `).run(status, String(err), retryCount + 1, id);
}

// ── Group JID cache ───────────────────────────────────────────────────────────
let groupCache = {};   // name → JID

async function refreshGroups(sock) {
    try {
        const groups = await sock.groupFetchAllParticipating();
        groupCache = {};
        for (const [jid, meta] of Object.entries(groups)) {
            groupCache[meta.subject] = jid;
        }
        logger.info({ count: Object.keys(groupCache).length }, 'Groups refreshed');
    } catch (e) {
        logger.warn({ err: e.message }, 'Failed to refresh groups');
    }
}

function findGroupJid(name) {
    // Exact match first
    if (groupCache[name]) return groupCache[name];
    // Case-insensitive fallback
    const lower = name.toLowerCase();
    for (const [subject, jid] of Object.entries(groupCache)) {
        if (subject.toLowerCase() === lower) return jid;
    }
    return null;
}

// ── Send helpers ──────────────────────────────────────────────────────────────
async function sendText(sock, jid, text) {
    await sock.sendMessage(jid, { text });
}

async function sendMedia(sock, jid, mediaPath, caption) {
    const ext = path.extname(mediaPath).toLowerCase();
    const isVideo = ['.mp4', '.mov', '.avi', '.mkv', '.3gp'].includes(ext);

    if (isVideo) {
        await sock.sendMessage(jid, {
            video: { stream: fs.createReadStream(mediaPath) },
            caption: caption || '',
            mimetype: 'video/mp4',
            fileLength: fs.statSync(mediaPath).size,
        });
    } else {
        await sock.sendMessage(jid, {
            image: { stream: fs.createReadStream(mediaPath) },
            caption: caption || '',
        });
    }
}

// ── Main sender loop ──────────────────────────────────────────────────────────
async function startSender() {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    logger.info({ version }, 'Starting Baileys sender');

    let sock = null;
    let isConnected = false;
    let groupsFetched = false;

    function createSocket() {
        sock = makeWASocket({
            version,
            auth: {
                creds: state.creds,
                keys: makeCacheableSignalKeyStore(state.keys, logger),
            },
            logger: pino({ level: 'silent' }),  // suppress Baileys internal logs
            printQRInTerminal: false,
            browser: ['WA Sender', 'Chrome', '124.0'],
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                console.log('\n── Scan this QR code with WhatsApp ──');
                qrcode.generate(qr, { small: true });
                console.log('────────────────────────────────────\n');
            }

            if (connection === 'open') {
                isConnected = true;
                logger.info('WhatsApp connected');
                if (!groupsFetched) {
                    await refreshGroups(sock);
                    groupsFetched = true;
                }
            }

            if (connection === 'close') {
                isConnected = false;
                const code = lastDisconnect?.error instanceof Boom
                    ? lastDisconnect.error.output?.statusCode
                    : null;
                const shouldReconnect = code !== DisconnectReason.loggedOut;
                logger.warn({ code }, `Connection closed. Reconnect: ${shouldReconnect}`);
                if (shouldReconnect) {
                    setTimeout(createSocket, 5000);
                } else {
                    logger.error('Logged out. Delete auth_state and restart to re-scan QR.');
                    process.exit(1);
                }
            }
        });
    }

    createSocket();

    // ── Poll loop ─────────────────────────────────────────────────────────────
    const db = openDb();
    logger.info({ db: DB_PATH, poll: POLL_MS }, 'Polling DB');

    async function poll() {
        if (!isConnected) {
            setTimeout(poll, POLL_MS);
            return;
        }

        let row;
        try {
            row = fetchNextPending(db);
        } catch (e) {
            logger.error({ err: e.message }, 'DB fetch error');
            setTimeout(poll, POLL_MS);
            return;
        }

        if (!row) {
            setTimeout(poll, POLL_MS);
            return;
        }

        logger.info({ id: row.id, group: row.group_name }, 'Processing message');

        try {
            let jid = findGroupJid(row.group_name);
            if (!jid) {
                // Refresh group list and retry once
                await refreshGroups(sock);
                jid = findGroupJid(row.group_name);
            }
            if (!jid) {
                throw new Error(`Group not found: "${row.group_name}"`);
            }

            if (row.media_path) {
                await sendMedia(sock, jid, resolveMediaPath(row.media_path), row.message_text);
            } else {
                await sendText(sock, jid, row.message_text);
            }

            markSent(db, row.id);
            logger.info({ id: row.id }, 'Sent OK');
        } catch (e) {
            logger.error({ id: row.id, err: e.message }, 'Send failed');
            markFailed(db, row.id, e.message, row.retry_count);
        }

        // Process next immediately, then yield
        setImmediate(() => setTimeout(poll, 100));
    }

    // Start polling after short delay to let connection establish
    setTimeout(poll, 5000);
}

startSender().catch((e) => {
    console.error('Fatal:', e);
    process.exit(1);
});
