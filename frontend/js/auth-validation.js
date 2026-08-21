(function (root, factory) {
    const api = factory();
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.InfoBankAuthValidation = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    const FIELD_LABELS = {
        username: 'Username',
        email: 'Email',
        password: 'Password',
    };

    function addError(errors, field, message) {
        if (!errors[field]) errors[field] = [];
        if (!errors[field].includes(message)) errors[field].push(message);
    }

    function validateRegistration(data) {
        const errors = {};
        const username = String(data?.username ?? '').trim();
        const email = String(data?.email ?? '').trim();
        const password = String(data?.password ?? '');

        if (username.length < 3) {
            addError(errors, 'username', 'Username must be at least 3 characters.');
        } else if (username.length > 100) {
            addError(errors, 'username', 'Username must be at most 100 characters.');
        } else if (!/^[A-Za-z0-9_.-]+$/.test(username)) {
            addError(errors, 'username', 'Use only letters, numbers, dots, hyphens, or underscores.');
        }

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            addError(errors, 'email', 'Enter a valid email address.');
        } else if (email.length > 255) {
            addError(errors, 'email', 'Email must be at most 255 characters.');
        }

        if (password.length < 12) {
            addError(errors, 'password', 'Password must be at least 12 characters.');
        } else if (password.length > 128) {
            addError(errors, 'password', 'Password must be at most 128 characters.');
        }

        return errors;
    }

    function fieldFromLocation(location) {
        if (!Array.isArray(location)) return null;
        for (let index = location.length - 1; index >= 0; index -= 1) {
            const candidate = location[index];
            if (typeof candidate === 'string' && FIELD_LABELS[candidate]) return candidate;
        }
        return null;
    }

    function friendlyValidationMessage(field, entry) {
        const type = String(entry?.type || '');
        const rawMessage = typeof entry?.msg === 'string' ? entry.msg.trim() : '';
        const limit = Number(entry?.ctx?.limit_value);

        if (field === 'email') return 'Enter a valid email address.';
        if (field === 'username' && type.includes('min_length')) {
            return `Username must be at least ${Number.isFinite(limit) ? limit : 3} characters.`;
        }
        if (field === 'username' && type.includes('max_length')) {
            return `Username must be at most ${Number.isFinite(limit) ? limit : 100} characters.`;
        }
        if (field === 'username' && type.includes('regex')) {
            return 'Use only letters, numbers, dots, hyphens, or underscores.';
        }
        if (field === 'password' && type.includes('min_length')) {
            return `Password must be at least ${Number.isFinite(limit) ? limit : 12} characters.`;
        }
        if (field === 'password' && type.includes('max_length')) {
            return `Password must be at most ${Number.isFinite(limit) ? limit : 128} characters.`;
        }
        if (field && rawMessage) return `${FIELD_LABELS[field]}: ${rawMessage}`;
        return rawMessage || 'The submitted value is invalid.';
    }

    function normalizeApiError(data, status) {
        const payload = data && typeof data === 'object' ? data : {};
        const safeError = payload.error && typeof payload.error === 'object' ? payload.error : {};
        const errorId = typeof safeError.error_id === 'string' ? safeError.error_id : '';

        if (typeof safeError.message === 'string' && safeError.message.trim()) {
            return {message: safeError.message.trim(), fieldErrors: {}, errorId};
        }

        if (Array.isArray(payload.detail)) {
            const fieldErrors = {};
            const messages = [];
            payload.detail.forEach(entry => {
                const field = fieldFromLocation(entry?.loc);
                const message = friendlyValidationMessage(field, entry);
                if (field) addError(fieldErrors, field, message);
                if (!messages.includes(message)) messages.push(message);
            });
            return {
                message: messages.join(' ') || `Request validation failed (HTTP ${status}).`,
                fieldErrors,
                errorId,
            };
        }

        if (typeof payload.detail === 'string' && payload.detail.trim()) {
            return {message: payload.detail.trim(), fieldErrors: {}, errorId};
        }
        if (payload.detail && typeof payload.detail === 'object' && typeof payload.detail.message === 'string') {
            return {message: payload.detail.message.trim(), fieldErrors: {}, errorId};
        }
        if (typeof payload.message === 'string' && payload.message.trim()) {
            return {message: payload.message.trim(), fieldErrors: {}, errorId};
        }
        return {message: `HTTP ${status}`, fieldErrors: {}, errorId};
    }

    return {
        normalizeApiError,
        validateRegistration,
    };
});
