const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
    normalizeApiError,
    validateRegistration,
} = require('../js/auth-validation.js');

test('the original fully invalid registration receives three readable field errors', () => {
    assert.deepEqual(validateRegistration({username: 'tv', email: 'tv', password: 'tv'}), {
        username: ['Username must be at least 3 characters.'],
        email: ['Enter a valid email address.'],
        password: ['Password must be at least 12 characters.'],
    });
});

test('a valid email leaves only username and password errors', () => {
    assert.deepEqual(validateRegistration({username: 'tv', email: 'tv@gmail.com', password: 'tv'}), {
        username: ['Username must be at least 3 characters.'],
        password: ['Password must be at least 12 characters.'],
    });
});

test('FastAPI 422 details become readable field errors instead of object coercions', () => {
    const normalized = normalizeApiError({
        detail: [
            {loc: ['body', 'username'], msg: 'ensure this value has at least 3 characters', type: 'value_error.any_str.min_length', ctx: {limit_value: 3}},
            {loc: ['body', 'password'], msg: 'ensure this value has at least 12 characters', type: 'value_error.any_str.min_length', ctx: {limit_value: 12}},
        ],
    }, 422);

    assert.deepEqual(normalized.fieldErrors, {
        username: ['Username must be at least 3 characters.'],
        password: ['Password must be at least 12 characters.'],
    });
    assert.equal(normalized.message.includes('[object Object]'), false);
    assert.match(normalized.message, /Username must be at least 3 characters/);
    assert.match(normalized.message, /Password must be at least 12 characters/);
});

test('safe backend error messages and error ids remain intact', () => {
    assert.deepEqual(normalizeApiError({
        error: {
            code: 'DATABASE_UNAVAILABLE',
            message: 'The database is temporarily unavailable.',
            error_id: 'safe-error-id',
        },
    }, 503), {
        message: 'The database is temporarily unavailable.',
        fieldErrors: {},
        errorId: 'safe-error-id',
    });
});

test('registration submit is intercepted before credentials can enter the URL', () => {
    const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
    const api = fs.readFileSync(path.join(__dirname, '..', 'js', 'api.js'), 'utf8');

    assert.match(html, /<form id="form-register"[^>]*novalidate>/);
    assert.doesNotMatch(html, /<form id="form-register"[^>]*onsubmit=/);
    assert.match(api, /addEventListener\('submit', event => \{\s*event\.preventDefault\(\);\s*void doRegister\(\);/);
});
