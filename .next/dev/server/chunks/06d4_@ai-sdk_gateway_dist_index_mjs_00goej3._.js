module.exports = [
"[project]/node_modules/.pnpm/@ai-sdk+gateway@3.0.104_zod@3.25.76/node_modules/@ai-sdk/gateway/dist/index.mjs [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "GatewayAuthenticationError",
    ()=>GatewayAuthenticationError,
    "GatewayError",
    ()=>GatewayError,
    "GatewayInternalServerError",
    ()=>GatewayInternalServerError,
    "GatewayInvalidRequestError",
    ()=>GatewayInvalidRequestError,
    "GatewayModelNotFoundError",
    ()=>GatewayModelNotFoundError,
    "GatewayRateLimitError",
    ()=>GatewayRateLimitError,
    "GatewayResponseError",
    ()=>GatewayResponseError,
    "createGateway",
    ()=>createGatewayProvider,
    "createGatewayProvider",
    ()=>createGatewayProvider,
    "gateway",
    ()=>gateway
]);
// src/gateway-provider.ts
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/@ai-sdk+provider-utils@4.0.23_zod@3.25.76/node_modules/@ai-sdk/provider-utils/dist/index.mjs [app-route] (ecmascript) <locals>");
// src/errors/as-gateway-error.ts
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$40$3$2e$0$2e$8$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/@ai-sdk+provider@3.0.8/node_modules/@ai-sdk/provider/dist/index.mjs [app-route] (ecmascript)");
// src/errors/create-gateway-error.ts
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/zod@3.25.76/node_modules/zod/v4/classic/external.js [app-route] (ecmascript) <export * as z>");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/zod@3.25.76/node_modules/zod/v3/external.js [app-route] (ecmascript) <export * as z>");
// src/vercel-environment.ts
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$vercel$2b$oidc$40$3$2e$2$2e$0$2f$node_modules$2f40$vercel$2f$oidc$2f$dist$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/@vercel+oidc@3.2.0/node_modules/@vercel/oidc/dist/index.js [app-route] (ecmascript)");
;
;
;
// src/errors/gateway-error.ts
var marker = "vercel.ai.gateway.error";
var symbol = Symbol.for(marker);
var _a, _b;
var GatewayError = class _GatewayError extends (_b = Error, _a = symbol, _b) {
    constructor({ message, statusCode = 500, cause, generationId }){
        super(generationId ? `${message} [${generationId}]` : message);
        this[_a] = true;
        this.statusCode = statusCode;
        this.cause = cause;
        this.generationId = generationId;
    }
    /**
   * Checks if the given error is a Gateway Error.
   * @param {unknown} error - The error to check.
   * @returns {boolean} True if the error is a Gateway Error, false otherwise.
   */ static isInstance(error) {
        return _GatewayError.hasMarker(error);
    }
    static hasMarker(error) {
        return typeof error === "object" && error !== null && symbol in error && error[symbol] === true;
    }
};
// src/errors/gateway-authentication-error.ts
var name = "GatewayAuthenticationError";
var marker2 = `vercel.ai.gateway.error.${name}`;
var symbol2 = Symbol.for(marker2);
var _a2, _b2;
var GatewayAuthenticationError = class _GatewayAuthenticationError extends (_b2 = GatewayError, _a2 = symbol2, _b2) {
    constructor({ message = "Authentication failed", statusCode = 401, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a2] = true;
        // used in isInstance
        this.name = name;
        this.type = "authentication_error";
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol2 in error;
    }
    /**
   * Creates a contextual error message when authentication fails
   */ static createContextualError({ apiKeyProvided, oidcTokenProvided, message = "Authentication failed", statusCode = 401, cause, generationId }) {
        let contextualMessage;
        if (apiKeyProvided) {
            contextualMessage = `AI Gateway authentication failed: Invalid API key.

Create a new API key: https://vercel.com/d?to=%2F%5Bteam%5D%2F%7E%2Fai%2Fapi-keys

Provide via 'apiKey' option or 'AI_GATEWAY_API_KEY' environment variable.`;
        } else if (oidcTokenProvided) {
            contextualMessage = `AI Gateway authentication failed: Invalid OIDC token.

Run 'npx vercel link' to link your project, then 'vc env pull' to fetch the token.

Alternatively, use an API key: https://vercel.com/d?to=%2F%5Bteam%5D%2F%7E%2Fai%2Fapi-keys`;
        } else {
            contextualMessage = `AI Gateway authentication failed: No authentication provided.

Option 1 - API key:
Create an API key: https://vercel.com/d?to=%2F%5Bteam%5D%2F%7E%2Fai%2Fapi-keys
Provide via 'apiKey' option or 'AI_GATEWAY_API_KEY' environment variable.

Option 2 - OIDC token:
Run 'npx vercel link' to link your project, then 'vc env pull' to fetch the token.`;
        }
        return new _GatewayAuthenticationError({
            message: contextualMessage,
            statusCode,
            cause,
            generationId
        });
    }
};
// src/errors/gateway-invalid-request-error.ts
var name2 = "GatewayInvalidRequestError";
var marker3 = `vercel.ai.gateway.error.${name2}`;
var symbol3 = Symbol.for(marker3);
var _a3, _b3;
var GatewayInvalidRequestError = class extends (_b3 = GatewayError, _a3 = symbol3, _b3) {
    constructor({ message = "Invalid request", statusCode = 400, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a3] = true;
        // used in isInstance
        this.name = name2;
        this.type = "invalid_request_error";
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol3 in error;
    }
};
// src/errors/gateway-rate-limit-error.ts
var name3 = "GatewayRateLimitError";
var marker4 = `vercel.ai.gateway.error.${name3}`;
var symbol4 = Symbol.for(marker4);
var _a4, _b4;
var GatewayRateLimitError = class extends (_b4 = GatewayError, _a4 = symbol4, _b4) {
    constructor({ message = "Rate limit exceeded", statusCode = 429, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a4] = true;
        // used in isInstance
        this.name = name3;
        this.type = "rate_limit_exceeded";
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol4 in error;
    }
};
;
;
var name4 = "GatewayModelNotFoundError";
var marker5 = `vercel.ai.gateway.error.${name4}`;
var symbol5 = Symbol.for(marker5);
var modelNotFoundParamSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        modelId: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
    })));
var _a5, _b5;
var GatewayModelNotFoundError = class extends (_b5 = GatewayError, _a5 = symbol5, _b5) {
    constructor({ message = "Model not found", statusCode = 404, modelId, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a5] = true;
        // used in isInstance
        this.name = name4;
        this.type = "model_not_found";
        this.modelId = modelId;
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol5 in error;
    }
};
// src/errors/gateway-internal-server-error.ts
var name5 = "GatewayInternalServerError";
var marker6 = `vercel.ai.gateway.error.${name5}`;
var symbol6 = Symbol.for(marker6);
var _a6, _b6;
var GatewayInternalServerError = class extends (_b6 = GatewayError, _a6 = symbol6, _b6) {
    constructor({ message = "Internal server error", statusCode = 500, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a6] = true;
        // used in isInstance
        this.name = name5;
        this.type = "internal_server_error";
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol6 in error;
    }
};
// src/errors/gateway-response-error.ts
var name6 = "GatewayResponseError";
var marker7 = `vercel.ai.gateway.error.${name6}`;
var symbol7 = Symbol.for(marker7);
var _a7, _b7;
var GatewayResponseError = class extends (_b7 = GatewayError, _a7 = symbol7, _b7) {
    constructor({ message = "Invalid response from Gateway", statusCode = 502, response, validationError, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a7] = true;
        // used in isInstance
        this.name = name6;
        this.type = "response_error";
        this.response = response;
        this.validationError = validationError;
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol7 in error;
    }
};
;
async function createGatewayErrorFromResponse({ response, statusCode, defaultMessage = "Gateway request failed", cause, authMethod }) {
    var _a9;
    const parseResult = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["safeValidateTypes"])({
        value: response,
        schema: gatewayErrorResponseSchema
    });
    if (!parseResult.success) {
        const rawGenerationId = typeof response === "object" && response !== null && "generationId" in response ? response.generationId : void 0;
        return new GatewayResponseError({
            message: `Invalid error response format: ${defaultMessage}`,
            statusCode,
            response,
            validationError: parseResult.error,
            cause,
            generationId: rawGenerationId
        });
    }
    const validatedResponse = parseResult.value;
    const errorType = validatedResponse.error.type;
    const message = validatedResponse.error.message;
    const generationId = (_a9 = validatedResponse.generationId) != null ? _a9 : void 0;
    switch(errorType){
        case "authentication_error":
            return GatewayAuthenticationError.createContextualError({
                apiKeyProvided: authMethod === "api-key",
                oidcTokenProvided: authMethod === "oidc",
                statusCode,
                cause,
                generationId
            });
        case "invalid_request_error":
            return new GatewayInvalidRequestError({
                message,
                statusCode,
                cause,
                generationId
            });
        case "rate_limit_exceeded":
            return new GatewayRateLimitError({
                message,
                statusCode,
                cause,
                generationId
            });
        case "model_not_found":
            {
                const modelResult = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["safeValidateTypes"])({
                    value: validatedResponse.error.param,
                    schema: modelNotFoundParamSchema
                });
                return new GatewayModelNotFoundError({
                    message,
                    statusCode,
                    modelId: modelResult.success ? modelResult.value.modelId : void 0,
                    cause,
                    generationId
                });
            }
        case "internal_server_error":
            return new GatewayInternalServerError({
                message,
                statusCode,
                cause,
                generationId
            });
        default:
            return new GatewayInternalServerError({
                message,
                statusCode,
                cause,
                generationId
            });
    }
}
var gatewayErrorResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        error: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            message: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullish(),
            param: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown().nullish(),
            code: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].union([
                __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number()
            ]).nullish()
        }),
        generationId: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullish()
    })));
// src/errors/gateway-timeout-error.ts
var name7 = "GatewayTimeoutError";
var marker8 = `vercel.ai.gateway.error.${name7}`;
var symbol8 = Symbol.for(marker8);
var _a8, _b8;
var GatewayTimeoutError = class _GatewayTimeoutError extends (_b8 = GatewayError, _a8 = symbol8, _b8) {
    constructor({ message = "Request timed out", statusCode = 408, cause, generationId } = {}){
        super({
            message,
            statusCode,
            cause,
            generationId
        });
        this[_a8] = true;
        // used in isInstance
        this.name = name7;
        this.type = "timeout_error";
    }
    static isInstance(error) {
        return GatewayError.hasMarker(error) && symbol8 in error;
    }
    /**
   * Creates a helpful timeout error message with troubleshooting guidance
   */ static createTimeoutError({ originalMessage, statusCode = 408, cause, generationId }) {
        const message = `Gateway request timed out: ${originalMessage}

    This is a client-side timeout. To resolve this, increase your timeout configuration: https://vercel.com/docs/ai-gateway/capabilities/video-generation#extending-timeouts-for-node.js`;
        return new _GatewayTimeoutError({
            message,
            statusCode,
            cause,
            generationId
        });
    }
};
// src/errors/as-gateway-error.ts
function isTimeoutError(error) {
    if (!(error instanceof Error)) {
        return false;
    }
    const errorCode = error.code;
    if (typeof errorCode === "string") {
        const undiciTimeoutCodes = [
            "UND_ERR_HEADERS_TIMEOUT",
            "UND_ERR_BODY_TIMEOUT",
            "UND_ERR_CONNECT_TIMEOUT"
        ];
        return undiciTimeoutCodes.includes(errorCode);
    }
    return false;
}
async function asGatewayError(error, authMethod) {
    var _a9;
    if (GatewayError.isInstance(error)) {
        return error;
    }
    if (isTimeoutError(error)) {
        return GatewayTimeoutError.createTimeoutError({
            originalMessage: error instanceof Error ? error.message : "Unknown error",
            cause: error
        });
    }
    if (__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$40$3$2e$0$2e$8$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__["APICallError"].isInstance(error)) {
        if (error.cause && isTimeoutError(error.cause)) {
            return GatewayTimeoutError.createTimeoutError({
                originalMessage: error.message,
                cause: error
            });
        }
        return await createGatewayErrorFromResponse({
            response: extractApiCallResponse(error),
            statusCode: (_a9 = error.statusCode) != null ? _a9 : 500,
            defaultMessage: "Gateway request failed",
            cause: error,
            authMethod
        });
    }
    return await createGatewayErrorFromResponse({
        response: {},
        statusCode: 500,
        defaultMessage: error instanceof Error ? `Gateway request failed: ${error.message}` : "Unknown Gateway error",
        cause: error,
        authMethod
    });
}
// src/errors/extract-api-call-response.ts
function extractApiCallResponse(error) {
    if (error.data !== void 0) {
        return error.data;
    }
    if (error.responseBody != null) {
        try {
            return JSON.parse(error.responseBody);
        } catch (e) {
            return error.responseBody;
        }
    }
    return {};
}
;
;
var GATEWAY_AUTH_METHOD_HEADER = "ai-gateway-auth-method";
async function parseAuthMethod(headers) {
    const result = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["safeValidateTypes"])({
        value: headers[GATEWAY_AUTH_METHOD_HEADER],
        schema: gatewayAuthMethodSchema
    });
    return result.success ? result.value : void 0;
}
var gatewayAuthMethodSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].union([
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("api-key"),
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("oidc")
    ])));
;
;
// src/gateway-model-entry.ts
var KNOWN_MODEL_TYPES = [
    "embedding",
    "image",
    "language",
    "reranking",
    "video"
];
// src/gateway-fetch-metadata.ts
var GatewayFetchMetadata = class {
    constructor(config){
        this.config = config;
    }
    async getAvailableModels() {
        try {
            const { value } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getFromApi"])({
                url: `${this.config.baseURL}/config`,
                headers: await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers()),
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewayAvailableModelsResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                fetch: this.config.fetch
            });
            return value;
        } catch (error) {
            throw await asGatewayError(error);
        }
    }
    async getCredits() {
        try {
            const baseUrl = new URL(this.config.baseURL);
            const { value } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getFromApi"])({
                url: `${baseUrl.origin}/v1/credits`,
                headers: await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers()),
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewayCreditsResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                fetch: this.config.fetch
            });
            return value;
        } catch (error) {
            throw await asGatewayError(error);
        }
    }
};
var gatewayAvailableModelsResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        models: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            id: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            name: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            description: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullish(),
            pricing: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                input: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                output: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                input_cache_read: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullish(),
                input_cache_write: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullish()
            }).transform(({ input, output, input_cache_read, input_cache_write })=>({
                    input,
                    output,
                    ...input_cache_read ? {
                        cachedInputTokens: input_cache_read
                    } : {},
                    ...input_cache_write ? {
                        cacheCreationInputTokens: input_cache_write
                    } : {}
                })).nullish(),
            specification: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                specificationVersion: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("v3"),
                provider: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                modelId: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
            }),
            modelType: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullish()
        })).transform((models)=>models.filter((m)=>m.modelType == null || KNOWN_MODEL_TYPES.includes(m.modelType)))
    })));
var gatewayCreditsResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        balance: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        total_used: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
    }).transform(({ balance, total_used })=>({
            balance,
            totalUsed: total_used
        }))));
;
;
var GatewaySpendReport = class {
    constructor(config){
        this.config = config;
    }
    async getSpendReport(params) {
        try {
            const baseUrl = new URL(this.config.baseURL);
            const searchParams = new URLSearchParams();
            searchParams.set("start_date", params.startDate);
            searchParams.set("end_date", params.endDate);
            if (params.groupBy) {
                searchParams.set("group_by", params.groupBy);
            }
            if (params.datePart) {
                searchParams.set("date_part", params.datePart);
            }
            if (params.userId) {
                searchParams.set("user_id", params.userId);
            }
            if (params.model) {
                searchParams.set("model", params.model);
            }
            if (params.provider) {
                searchParams.set("provider", params.provider);
            }
            if (params.credentialType) {
                searchParams.set("credential_type", params.credentialType);
            }
            if (params.tags && params.tags.length > 0) {
                searchParams.set("tags", params.tags.join(","));
            }
            const { value } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getFromApi"])({
                url: `${baseUrl.origin}/v1/report?${searchParams.toString()}`,
                headers: await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers()),
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewaySpendReportResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                fetch: this.config.fetch
            });
            return value;
        } catch (error) {
            throw await asGatewayError(error);
        }
    }
};
var gatewaySpendReportResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        results: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            day: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
            hour: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
            user: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
            model: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
            tag: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
            provider: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
            credential_type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
                "byok",
                "system"
            ]).optional(),
            total_cost: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            market_cost: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            input_tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            output_tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            cached_input_tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            cache_creation_input_tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            reasoning_tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            request_count: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional()
        }).transform(({ credential_type, total_cost, market_cost, input_tokens, output_tokens, cached_input_tokens, cache_creation_input_tokens, reasoning_tokens, request_count, ...rest })=>({
                ...rest,
                ...credential_type !== void 0 ? {
                    credentialType: credential_type
                } : {},
                totalCost: total_cost,
                ...market_cost !== void 0 ? {
                    marketCost: market_cost
                } : {},
                ...input_tokens !== void 0 ? {
                    inputTokens: input_tokens
                } : {},
                ...output_tokens !== void 0 ? {
                    outputTokens: output_tokens
                } : {},
                ...cached_input_tokens !== void 0 ? {
                    cachedInputTokens: cached_input_tokens
                } : {},
                ...cache_creation_input_tokens !== void 0 ? {
                    cacheCreationInputTokens: cache_creation_input_tokens
                } : {},
                ...reasoning_tokens !== void 0 ? {
                    reasoningTokens: reasoning_tokens
                } : {},
                ...request_count !== void 0 ? {
                    requestCount: request_count
                } : {}
            })))
    })));
;
;
var GatewayGenerationInfoFetcher = class {
    constructor(config){
        this.config = config;
    }
    async getGenerationInfo(params) {
        try {
            const baseUrl = new URL(this.config.baseURL);
            const { value } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getFromApi"])({
                url: `${baseUrl.origin}/v1/generation?id=${encodeURIComponent(params.id)}`,
                headers: await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers()),
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewayGenerationInfoResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                fetch: this.config.fetch
            });
            return value;
        } catch (error) {
            throw await asGatewayError(error);
        }
    }
};
var gatewayGenerationInfoResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        data: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            id: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            total_cost: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            upstream_inference_cost: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            usage: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            created_at: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            model: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            is_byok: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].boolean(),
            provider_name: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            streamed: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].boolean(),
            finish_reason: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            latency: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            generation_time: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            native_tokens_prompt: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            native_tokens_completion: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            native_tokens_reasoning: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            native_tokens_cached: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            native_tokens_cache_creation: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            billable_web_search_calls: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number()
        }).transform(({ total_cost, upstream_inference_cost, created_at, is_byok, provider_name, finish_reason, generation_time, native_tokens_prompt, native_tokens_completion, native_tokens_reasoning, native_tokens_cached, native_tokens_cache_creation, billable_web_search_calls, ...rest })=>({
                ...rest,
                totalCost: total_cost,
                upstreamInferenceCost: upstream_inference_cost,
                createdAt: created_at,
                isByok: is_byok,
                providerName: provider_name,
                finishReason: finish_reason,
                generationTime: generation_time,
                promptTokens: native_tokens_prompt,
                completionTokens: native_tokens_completion,
                reasoningTokens: native_tokens_reasoning,
                cachedTokens: native_tokens_cached,
                cacheCreationTokens: native_tokens_cache_creation,
                billableWebSearchCalls: billable_web_search_calls
            }))
    }).transform(({ data })=>data)));
;
;
var GatewayLanguageModel = class {
    constructor(modelId, config){
        this.modelId = modelId;
        this.config = config;
        this.specificationVersion = "v3";
        this.supportedUrls = {
            "*/*": [
                /.*/
            ]
        };
    }
    get provider() {
        return this.config.provider;
    }
    async getArgs(options) {
        const { abortSignal: _abortSignal, ...optionsWithoutSignal } = options;
        return {
            args: this.maybeEncodeFileParts(optionsWithoutSignal),
            warnings: []
        };
    }
    async doGenerate(options) {
        const { args, warnings } = await this.getArgs(options);
        const { abortSignal } = options;
        const resolvedHeaders = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers());
        try {
            const { responseHeaders, value: responseBody, rawValue: rawResponse } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["postJsonToApi"])({
                url: this.getUrl(),
                headers: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineHeaders"])(resolvedHeaders, options.headers, this.getModelConfigHeaders(this.modelId, false), await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.o11yHeaders)),
                body: args,
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                ...abortSignal && {
                    abortSignal
                },
                fetch: this.config.fetch
            });
            return {
                ...responseBody,
                request: {
                    body: args
                },
                response: {
                    headers: responseHeaders,
                    body: rawResponse
                },
                warnings
            };
        } catch (error) {
            throw await asGatewayError(error, await parseAuthMethod(resolvedHeaders));
        }
    }
    async doStream(options) {
        const { args, warnings } = await this.getArgs(options);
        const { abortSignal } = options;
        const resolvedHeaders = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers());
        try {
            const { value: response, responseHeaders } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["postJsonToApi"])({
                url: this.getUrl(),
                headers: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineHeaders"])(resolvedHeaders, options.headers, this.getModelConfigHeaders(this.modelId, true), await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.o11yHeaders)),
                body: args,
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createEventSourceResponseHandler"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any()),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                ...abortSignal && {
                    abortSignal
                },
                fetch: this.config.fetch
            });
            return {
                stream: response.pipeThrough(new TransformStream({
                    start (controller) {
                        if (warnings.length > 0) {
                            controller.enqueue({
                                type: "stream-start",
                                warnings
                            });
                        }
                    },
                    transform (chunk, controller) {
                        if (chunk.success) {
                            const streamPart = chunk.value;
                            if (streamPart.type === "raw" && !options.includeRawChunks) {
                                return;
                            }
                            if (streamPart.type === "response-metadata" && streamPart.timestamp && typeof streamPart.timestamp === "string") {
                                streamPart.timestamp = new Date(streamPart.timestamp);
                            }
                            controller.enqueue(streamPart);
                        } else {
                            controller.error(chunk.error);
                        }
                    }
                })),
                request: {
                    body: args
                },
                response: {
                    headers: responseHeaders
                }
            };
        } catch (error) {
            throw await asGatewayError(error, await parseAuthMethod(resolvedHeaders));
        }
    }
    isFilePart(part) {
        return part && typeof part === "object" && "type" in part && part.type === "file";
    }
    /**
   * Encodes file parts in the prompt to base64. Mutates the passed options
   * instance directly to avoid copying the file data.
   * @param options - The options to encode.
   * @returns The options with the file parts encoded.
   */ maybeEncodeFileParts(options) {
        for (const message of options.prompt){
            for (const part of message.content){
                if (this.isFilePart(part)) {
                    const filePart = part;
                    if (filePart.data instanceof Uint8Array) {
                        const buffer = Uint8Array.from(filePart.data);
                        const base64Data = Buffer.from(buffer).toString("base64");
                        filePart.data = new URL(`data:${filePart.mediaType || "application/octet-stream"};base64,${base64Data}`);
                    }
                }
            }
        }
        return options;
    }
    getUrl() {
        return `${this.config.baseURL}/language-model`;
    }
    getModelConfigHeaders(modelId, streaming) {
        return {
            "ai-language-model-specification-version": "3",
            "ai-language-model-id": modelId,
            "ai-language-model-streaming": String(streaming)
        };
    }
};
;
;
var GatewayEmbeddingModel = class {
    constructor(modelId, config){
        this.modelId = modelId;
        this.config = config;
        this.specificationVersion = "v3";
        this.maxEmbeddingsPerCall = 2048;
        this.supportsParallelCalls = true;
    }
    get provider() {
        return this.config.provider;
    }
    async doEmbed({ values, headers, abortSignal, providerOptions }) {
        var _a9;
        const resolvedHeaders = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers());
        try {
            const { responseHeaders, value: responseBody, rawValue } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["postJsonToApi"])({
                url: this.getUrl(),
                headers: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineHeaders"])(resolvedHeaders, headers != null ? headers : {}, this.getModelConfigHeaders(), await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.o11yHeaders)),
                body: {
                    values,
                    ...providerOptions ? {
                        providerOptions
                    } : {}
                },
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewayEmbeddingResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                ...abortSignal && {
                    abortSignal
                },
                fetch: this.config.fetch
            });
            return {
                embeddings: responseBody.embeddings,
                usage: (_a9 = responseBody.usage) != null ? _a9 : void 0,
                providerMetadata: responseBody.providerMetadata,
                response: {
                    headers: responseHeaders,
                    body: rawValue
                },
                warnings: []
            };
        } catch (error) {
            throw await asGatewayError(error, await parseAuthMethod(resolvedHeaders));
        }
    }
    getUrl() {
        return `${this.config.baseURL}/embedding-model`;
    }
    getModelConfigHeaders() {
        return {
            "ai-embedding-model-specification-version": "3",
            "ai-model-id": this.modelId
        };
    }
};
var gatewayEmbeddingResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        embeddings: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number())),
        usage: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number()
        }).nullish(),
        providerMetadata: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown())).optional()
    })));
;
;
var GatewayImageModel = class {
    constructor(modelId, config){
        this.modelId = modelId;
        this.config = config;
        this.specificationVersion = "v3";
        // Set a very large number to prevent client-side splitting of requests
        this.maxImagesPerCall = Number.MAX_SAFE_INTEGER;
    }
    get provider() {
        return this.config.provider;
    }
    async doGenerate({ prompt, n, size, aspectRatio, seed, files, mask, providerOptions, headers, abortSignal }) {
        var _a9, _b9, _c, _d;
        const resolvedHeaders = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers());
        try {
            const { responseHeaders, value: responseBody, rawValue } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["postJsonToApi"])({
                url: this.getUrl(),
                headers: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineHeaders"])(resolvedHeaders, headers != null ? headers : {}, this.getModelConfigHeaders(), await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.o11yHeaders)),
                body: {
                    prompt,
                    n,
                    ...size && {
                        size
                    },
                    ...aspectRatio && {
                        aspectRatio
                    },
                    ...seed && {
                        seed
                    },
                    ...providerOptions && {
                        providerOptions
                    },
                    ...files && {
                        files: files.map((file)=>maybeEncodeImageFile(file))
                    },
                    ...mask && {
                        mask: maybeEncodeImageFile(mask)
                    }
                },
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewayImageResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                ...abortSignal && {
                    abortSignal
                },
                fetch: this.config.fetch
            });
            return {
                images: responseBody.images,
                // Always base64 strings from server
                warnings: (_a9 = responseBody.warnings) != null ? _a9 : [],
                providerMetadata: responseBody.providerMetadata,
                response: {
                    timestamp: /* @__PURE__ */ new Date(),
                    modelId: this.modelId,
                    headers: responseHeaders
                },
                ...responseBody.usage != null && {
                    usage: {
                        inputTokens: (_b9 = responseBody.usage.inputTokens) != null ? _b9 : void 0,
                        outputTokens: (_c = responseBody.usage.outputTokens) != null ? _c : void 0,
                        totalTokens: (_d = responseBody.usage.totalTokens) != null ? _d : void 0
                    }
                }
            };
        } catch (error) {
            throw await asGatewayError(error, await parseAuthMethod(resolvedHeaders));
        }
    }
    getUrl() {
        return `${this.config.baseURL}/image-model`;
    }
    getModelConfigHeaders() {
        return {
            "ai-image-model-specification-version": "3",
            "ai-model-id": this.modelId
        };
    }
};
function maybeEncodeImageFile(file) {
    if (file.type === "file" && file.data instanceof Uint8Array) {
        return {
            ...file,
            data: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["convertUint8ArrayToBase64"])(file.data)
        };
    }
    return file;
}
var providerMetadataEntrySchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
    images: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown()).optional()
}).catchall(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown());
var gatewayImageWarningSchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].discriminatedUnion("type", [
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("unsupported"),
        feature: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        details: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("compatibility"),
        feature: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        details: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("other"),
        message: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
    })
]);
var gatewayImageUsageSchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
    inputTokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().nullish(),
    outputTokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().nullish(),
    totalTokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().nullish()
});
var gatewayImageResponseSchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
    images: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()),
    // Always base64 strings over the wire
    warnings: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(gatewayImageWarningSchema).optional(),
    providerMetadata: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), providerMetadataEntrySchema).optional(),
    usage: gatewayImageUsageSchema.optional()
});
;
;
;
var GatewayVideoModel = class {
    constructor(modelId, config){
        this.modelId = modelId;
        this.config = config;
        this.specificationVersion = "v3";
        // Set a very large number to prevent client-side splitting of requests
        this.maxVideosPerCall = Number.MAX_SAFE_INTEGER;
    }
    get provider() {
        return this.config.provider;
    }
    async doGenerate({ prompt, n, aspectRatio, resolution, duration, fps, seed, image, providerOptions, headers, abortSignal }) {
        var _a9;
        const resolvedHeaders = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers());
        try {
            const { responseHeaders, value: responseBody } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["postJsonToApi"])({
                url: this.getUrl(),
                headers: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineHeaders"])(resolvedHeaders, headers != null ? headers : {}, this.getModelConfigHeaders(), await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.o11yHeaders), {
                    accept: "text/event-stream"
                }),
                body: {
                    prompt,
                    n,
                    ...aspectRatio && {
                        aspectRatio
                    },
                    ...resolution && {
                        resolution
                    },
                    ...duration && {
                        duration
                    },
                    ...fps && {
                        fps
                    },
                    ...seed && {
                        seed
                    },
                    ...providerOptions && {
                        providerOptions
                    },
                    ...image && {
                        image: maybeEncodeVideoFile(image)
                    }
                },
                successfulResponseHandler: async ({ response, url, requestBodyValues })=>{
                    if (response.body == null) {
                        throw new __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$40$3$2e$0$2e$8$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__["APICallError"]({
                            message: "SSE response body is empty",
                            url,
                            requestBodyValues,
                            statusCode: response.status
                        });
                    }
                    const eventStream = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["parseJsonEventStream"])({
                        stream: response.body,
                        schema: gatewayVideoEventSchema
                    });
                    const reader = eventStream.getReader();
                    const { done, value: parseResult } = await reader.read();
                    reader.releaseLock();
                    if (done || !parseResult) {
                        throw new __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$40$3$2e$0$2e$8$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__["APICallError"]({
                            message: "SSE stream ended without a data event",
                            url,
                            requestBodyValues,
                            statusCode: response.status
                        });
                    }
                    if (!parseResult.success) {
                        throw new __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$40$3$2e$0$2e$8$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__["APICallError"]({
                            message: "Failed to parse video SSE event",
                            cause: parseResult.error,
                            url,
                            requestBodyValues,
                            statusCode: response.status
                        });
                    }
                    const event = parseResult.value;
                    if (event.type === "error") {
                        throw new __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$40$3$2e$0$2e$8$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__["APICallError"]({
                            message: event.message,
                            statusCode: event.statusCode,
                            url,
                            requestBodyValues,
                            responseHeaders: Object.fromEntries([
                                ...response.headers
                            ]),
                            responseBody: JSON.stringify(event),
                            data: {
                                error: {
                                    message: event.message,
                                    type: event.errorType,
                                    param: event.param
                                }
                            }
                        });
                    }
                    return {
                        value: {
                            videos: event.videos,
                            warnings: event.warnings,
                            providerMetadata: event.providerMetadata
                        },
                        responseHeaders: Object.fromEntries([
                            ...response.headers
                        ])
                    };
                },
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                ...abortSignal && {
                    abortSignal
                },
                fetch: this.config.fetch
            });
            return {
                videos: responseBody.videos,
                warnings: (_a9 = responseBody.warnings) != null ? _a9 : [],
                providerMetadata: responseBody.providerMetadata,
                response: {
                    timestamp: /* @__PURE__ */ new Date(),
                    modelId: this.modelId,
                    headers: responseHeaders
                }
            };
        } catch (error) {
            throw await asGatewayError(error, await parseAuthMethod(resolvedHeaders));
        }
    }
    getUrl() {
        return `${this.config.baseURL}/video-model`;
    }
    getModelConfigHeaders() {
        return {
            "ai-video-model-specification-version": "3",
            "ai-model-id": this.modelId
        };
    }
};
function maybeEncodeVideoFile(file) {
    if (file.type === "file" && file.data instanceof Uint8Array) {
        return {
            ...file,
            data: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["convertUint8ArrayToBase64"])(file.data)
        };
    }
    return file;
}
var providerMetadataEntrySchema2 = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
    videos: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown()).optional()
}).catchall(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown());
var gatewayVideoDataSchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].union([
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("url"),
        url: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        mediaType: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("base64"),
        data: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        mediaType: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
    })
]);
var gatewayVideoWarningSchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].discriminatedUnion("type", [
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("unsupported"),
        feature: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        details: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("compatibility"),
        feature: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        details: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("other"),
        message: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
    })
]);
var gatewayVideoEventSchema = __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].discriminatedUnion("type", [
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("result"),
        videos: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(gatewayVideoDataSchema),
        warnings: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(gatewayVideoWarningSchema).optional(),
        providerMetadata: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), providerMetadataEntrySchema2).optional()
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        type: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].literal("error"),
        message: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        errorType: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
        statusCode: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
        param: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown().nullable()
    })
]);
;
;
var GatewayRerankingModel = class {
    constructor(modelId, config){
        this.modelId = modelId;
        this.config = config;
        this.specificationVersion = "v3";
    }
    get provider() {
        return this.config.provider;
    }
    async doRerank({ documents, query, topN, headers, abortSignal, providerOptions }) {
        const resolvedHeaders = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.headers());
        try {
            const { responseHeaders, value: responseBody, rawValue } = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["postJsonToApi"])({
                url: this.getUrl(),
                headers: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["combineHeaders"])(resolvedHeaders, headers != null ? headers : {}, this.getModelConfigHeaders(), await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["resolve"])(this.config.o11yHeaders)),
                body: {
                    documents,
                    query,
                    ...topN != null ? {
                        topN
                    } : {},
                    ...providerOptions ? {
                        providerOptions
                    } : {}
                },
                successfulResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonResponseHandler"])(gatewayRerankingResponseSchema),
                failedResponseHandler: (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createJsonErrorResponseHandler"])({
                    errorSchema: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].any(),
                    errorToMessage: (data)=>data
                }),
                ...abortSignal && {
                    abortSignal
                },
                fetch: this.config.fetch
            });
            return {
                ranking: responseBody.ranking,
                providerMetadata: responseBody.providerMetadata,
                response: {
                    headers: responseHeaders,
                    body: rawValue
                },
                warnings: []
            };
        } catch (error) {
            throw await asGatewayError(error, await parseAuthMethod(resolvedHeaders));
        }
    }
    getUrl() {
        return `${this.config.baseURL}/reranking-model`;
    }
    getModelConfigHeaders() {
        return {
            "ai-reranking-model-specification-version": "3",
            "ai-model-id": this.modelId
        };
    }
};
var gatewayRerankingResponseSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        ranking: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            index: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number(),
            relevanceScore: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number()
        })),
        providerMetadata: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].record(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(), __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v4$2f$classic$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].unknown())).optional()
    })));
;
;
var parallelSearchInputSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        objective: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().describe("Natural-language description of the web research goal, including source or freshness guidance and broader context from the task. Maximum 5000 characters."),
        search_queries: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()).optional().describe("Optional search queries to supplement the objective. Maximum 200 characters per query."),
        mode: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
            "one-shot",
            "agentic"
        ]).optional().describe('Mode preset: "one-shot" for comprehensive results with longer excerpts (default), "agentic" for concise, token-efficient results for multi-step workflows.'),
        max_results: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum number of results to return (1-20). Defaults to 10 if not specified."),
        source_policy: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            include_domains: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()).optional().describe("List of domains to include in search results."),
            exclude_domains: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()).optional().describe("List of domains to exclude from search results."),
            after_date: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional().describe("Only include results published after this date (ISO 8601 format).")
        }).optional().describe("Source policy for controlling which domains to include/exclude and freshness."),
        excerpts: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            max_chars_per_result: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum characters per result."),
            max_chars_total: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum total characters across all results.")
        }).optional().describe("Excerpt configuration for controlling result length."),
        fetch_policy: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            max_age_seconds: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum age in seconds for cached content. Set to 0 to always fetch fresh content.")
        }).optional().describe("Fetch policy for controlling content freshness.")
    })));
var parallelSearchOutputSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].union([
        // Success response
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            searchId: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            results: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                url: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                title: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                excerpt: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                publishDate: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().nullable().optional(),
                relevanceScore: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional()
            }))
        }),
        // Error response
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            error: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
                "api_error",
                "rate_limit",
                "timeout",
                "invalid_input",
                "configuration_error",
                "unknown"
            ]),
            statusCode: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            message: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
        })
    ])));
var parallelSearchToolFactory = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createProviderToolFactoryWithOutputSchema"])({
    id: "gateway.parallel_search",
    inputSchema: parallelSearchInputSchema,
    outputSchema: parallelSearchOutputSchema
});
var parallelSearch = (config = {})=>parallelSearchToolFactory(config);
;
;
var perplexitySearchInputSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
        query: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].union([
            __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
            __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string())
        ]).describe("Search query (string) or multiple queries (array of up to 5 strings). Multi-query searches return combined results from all queries."),
        max_results: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum number of search results to return (1-20, default: 10)"),
        max_tokens_per_page: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum number of tokens to extract per search result page (256-2048, default: 2048)"),
        max_tokens: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional().describe("Maximum total tokens across all search results (default: 25000, max: 1000000)"),
        country: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional().describe("Two-letter ISO 3166-1 alpha-2 country code for regional search results (e.g., 'US', 'GB', 'FR')"),
        search_domain_filter: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()).optional().describe("List of domains to include or exclude from search results (max 20). To include: ['nature.com', 'science.org']. To exclude: ['-example.com', '-spam.net']"),
        search_language_filter: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()).optional().describe("List of ISO 639-1 language codes to filter results (max 10, lowercase). Examples: ['en', 'fr', 'de']"),
        search_after_date: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional().describe("Include only results published after this date. Format: 'MM/DD/YYYY' (e.g., '3/1/2025'). Cannot be used with search_recency_filter."),
        search_before_date: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional().describe("Include only results published before this date. Format: 'MM/DD/YYYY' (e.g., '3/15/2025'). Cannot be used with search_recency_filter."),
        last_updated_after_filter: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional().describe("Include only results last updated after this date. Format: 'MM/DD/YYYY' (e.g., '3/1/2025'). Cannot be used with search_recency_filter."),
        last_updated_before_filter: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional().describe("Include only results last updated before this date. Format: 'MM/DD/YYYY' (e.g., '3/15/2025'). Cannot be used with search_recency_filter."),
        search_recency_filter: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
            "day",
            "week",
            "month",
            "year"
        ]).optional().describe("Filter results by relative time period. Cannot be used with search_after_date or search_before_date.")
    })));
var perplexitySearchOutputSchema = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lazySchema"])(()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["zodSchema"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].union([
        // Success response
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            results: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].array(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
                title: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                url: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                snippet: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string(),
                date: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional(),
                lastUpdated: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string().optional()
            })),
            id: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
        }),
        // Error response
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].object({
            error: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].enum([
                "api_error",
                "rate_limit",
                "timeout",
                "invalid_input",
                "unknown"
            ]),
            statusCode: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].number().optional(),
            message: __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$zod$40$3$2e$25$2e$76$2f$node_modules$2f$zod$2f$v3$2f$external$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$export__$2a$__as__z$3e$__["z"].string()
        })
    ])));
var perplexitySearchToolFactory = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createProviderToolFactoryWithOutputSchema"])({
    id: "gateway.perplexity_search",
    inputSchema: perplexitySearchInputSchema,
    outputSchema: perplexitySearchOutputSchema
});
var perplexitySearch = (config = {})=>perplexitySearchToolFactory(config);
// src/gateway-tools.ts
var gatewayTools = {
    /**
   * Search the web using Parallel AI's Search API for LLM-optimized excerpts.
   *
   * Takes a natural language objective and returns relevant excerpts,
   * replacing multiple keyword searches with a single call for broad
   * or complex queries. Supports different search types for depth vs
   * breadth tradeoffs.
   */ parallelSearch,
    /**
   * Search the web using Perplexity's Search API for real-time information,
   * news, research papers, and articles.
   *
   * Provides ranked search results with advanced filtering options including
   * domain, language, date range, and recency filters.
   */ perplexitySearch
};
;
;
async function getVercelRequestId() {
    var _a9;
    return (_a9 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$vercel$2b$oidc$40$3$2e$2$2e$0$2f$node_modules$2f40$vercel$2f$oidc$2f$dist$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getContext"])().headers) == null ? void 0 : _a9["x-vercel-id"];
}
;
// src/version.ts
var VERSION = ("TURBOPACK compile-time truthy", 1) ? "3.0.104" : "TURBOPACK unreachable";
// src/gateway-provider.ts
var AI_GATEWAY_PROTOCOL_VERSION = "0.0.1";
function createGatewayProvider(options = {}) {
    var _a9, _b9;
    let pendingMetadata = null;
    let metadataCache = null;
    const cacheRefreshMillis = (_a9 = options.metadataCacheRefreshMillis) != null ? _a9 : 1e3 * 60 * 5;
    let lastFetchTime = 0;
    const baseURL = (_b9 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["withoutTrailingSlash"])(options.baseURL)) != null ? _b9 : "https://ai-gateway.vercel.sh/v3/ai";
    const getHeaders = async ()=>{
        try {
            const auth = await getGatewayAuthToken(options);
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["withUserAgentSuffix"])({
                Authorization: `Bearer ${auth.token}`,
                "ai-gateway-protocol-version": AI_GATEWAY_PROTOCOL_VERSION,
                [GATEWAY_AUTH_METHOD_HEADER]: auth.authMethod,
                ...options.headers
            }, `ai-sdk/gateway/${VERSION}`);
        } catch (error) {
            throw GatewayAuthenticationError.createContextualError({
                apiKeyProvided: false,
                oidcTokenProvided: false,
                statusCode: 401,
                cause: error
            });
        }
    };
    const createO11yHeaders = ()=>{
        const deploymentId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["loadOptionalSetting"])({
            settingValue: void 0,
            environmentVariableName: "VERCEL_DEPLOYMENT_ID"
        });
        const environment = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["loadOptionalSetting"])({
            settingValue: void 0,
            environmentVariableName: "VERCEL_ENV"
        });
        const region = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["loadOptionalSetting"])({
            settingValue: void 0,
            environmentVariableName: "VERCEL_REGION"
        });
        const projectId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["loadOptionalSetting"])({
            settingValue: void 0,
            environmentVariableName: "VERCEL_PROJECT_ID"
        });
        return async ()=>{
            const requestId = await getVercelRequestId();
            return {
                ...deploymentId && {
                    "ai-o11y-deployment-id": deploymentId
                },
                ...environment && {
                    "ai-o11y-environment": environment
                },
                ...region && {
                    "ai-o11y-region": region
                },
                ...requestId && {
                    "ai-o11y-request-id": requestId
                },
                ...projectId && {
                    "ai-o11y-project-id": projectId
                }
            };
        };
    };
    const createLanguageModel = (modelId)=>{
        return new GatewayLanguageModel(modelId, {
            provider: "gateway",
            baseURL,
            headers: getHeaders,
            fetch: options.fetch,
            o11yHeaders: createO11yHeaders()
        });
    };
    const getAvailableModels = async ()=>{
        var _a10, _b10, _c;
        const now = (_c = (_b10 = (_a10 = options._internal) == null ? void 0 : _a10.currentDate) == null ? void 0 : _b10.call(_a10).getTime()) != null ? _c : Date.now();
        if (!pendingMetadata || now - lastFetchTime > cacheRefreshMillis) {
            lastFetchTime = now;
            pendingMetadata = new GatewayFetchMetadata({
                baseURL,
                headers: getHeaders,
                fetch: options.fetch
            }).getAvailableModels().then((metadata)=>{
                metadataCache = metadata;
                return metadata;
            }).catch(async (error)=>{
                throw await asGatewayError(error, await parseAuthMethod(await getHeaders()));
            });
        }
        return metadataCache ? Promise.resolve(metadataCache) : pendingMetadata;
    };
    const getCredits = async ()=>{
        return new GatewayFetchMetadata({
            baseURL,
            headers: getHeaders,
            fetch: options.fetch
        }).getCredits().catch(async (error)=>{
            throw await asGatewayError(error, await parseAuthMethod(await getHeaders()));
        });
    };
    const getSpendReport = async (params)=>{
        return new GatewaySpendReport({
            baseURL,
            headers: getHeaders,
            fetch: options.fetch
        }).getSpendReport(params).catch(async (error)=>{
            throw await asGatewayError(error, await parseAuthMethod(await getHeaders()));
        });
    };
    const getGenerationInfo = async (params)=>{
        return new GatewayGenerationInfoFetcher({
            baseURL,
            headers: getHeaders,
            fetch: options.fetch
        }).getGenerationInfo(params).catch(async (error)=>{
            throw await asGatewayError(error, await parseAuthMethod(await getHeaders()));
        });
    };
    const provider = function(modelId) {
        if (new.target) {
            throw new Error("The Gateway Provider model function cannot be called with the new keyword.");
        }
        return createLanguageModel(modelId);
    };
    provider.specificationVersion = "v3";
    provider.getAvailableModels = getAvailableModels;
    provider.getCredits = getCredits;
    provider.getSpendReport = getSpendReport;
    provider.getGenerationInfo = getGenerationInfo;
    provider.imageModel = (modelId)=>{
        return new GatewayImageModel(modelId, {
            provider: "gateway",
            baseURL,
            headers: getHeaders,
            fetch: options.fetch,
            o11yHeaders: createO11yHeaders()
        });
    };
    provider.languageModel = createLanguageModel;
    const createEmbeddingModel = (modelId)=>{
        return new GatewayEmbeddingModel(modelId, {
            provider: "gateway",
            baseURL,
            headers: getHeaders,
            fetch: options.fetch,
            o11yHeaders: createO11yHeaders()
        });
    };
    provider.embeddingModel = createEmbeddingModel;
    provider.textEmbeddingModel = createEmbeddingModel;
    provider.videoModel = (modelId)=>{
        return new GatewayVideoModel(modelId, {
            provider: "gateway",
            baseURL,
            headers: getHeaders,
            fetch: options.fetch,
            o11yHeaders: createO11yHeaders()
        });
    };
    const createRerankingModel = (modelId)=>{
        return new GatewayRerankingModel(modelId, {
            provider: "gateway",
            baseURL,
            headers: getHeaders,
            fetch: options.fetch,
            o11yHeaders: createO11yHeaders()
        });
    };
    provider.rerankingModel = createRerankingModel;
    provider.reranking = createRerankingModel;
    provider.chat = provider.languageModel;
    provider.embedding = provider.embeddingModel;
    provider.image = provider.imageModel;
    provider.video = provider.videoModel;
    provider.tools = gatewayTools;
    return provider;
}
var gateway = createGatewayProvider();
async function getGatewayAuthToken(options) {
    const apiKey = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$ai$2d$sdk$2b$provider$2d$utils$40$4$2e$0$2e$23_zod$40$3$2e$25$2e$76$2f$node_modules$2f40$ai$2d$sdk$2f$provider$2d$utils$2f$dist$2f$index$2e$mjs__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["loadOptionalSetting"])({
        settingValue: options.apiKey,
        environmentVariableName: "AI_GATEWAY_API_KEY"
    });
    if (apiKey) {
        return {
            token: apiKey,
            authMethod: "api-key"
        };
    }
    const oidcToken = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f40$vercel$2b$oidc$40$3$2e$2$2e$0$2f$node_modules$2f40$vercel$2f$oidc$2f$dist$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getVercelOidcToken"])();
    return {
        token: oidcToken,
        authMethod: "oidc"
    };
}
;
}),
];

//# sourceMappingURL=06d4_%40ai-sdk_gateway_dist_index_mjs_00goej3._.js.map