import assert from 'node:assert/strict';
import {normalizeLimits} from './openai-usage.mjs';
const result=normalizeLimits({accountId:'private',rateLimitsByLimitId:{codex:{limitId:'codex',primary:{usedPercent:9,windowDurationMins:300,resetsAt:1794569075},secondary:{usedPercent:101,windowDurationMins:10080},credits:{hasCredits:false,unlimited:false,balance:'0',secret:'omit'}}},rateLimitResetCredits:{availableCount:1,credits:[{id:'private'}]}});
assert.equal(result.buckets[0].primary.remainingPercent,91);assert.equal(result.buckets[0].secondary.remainingPercent,0);assert.equal(result.availableResets,1);assert.equal(result.buckets[0].credits.balance,'0');assert.ok(!JSON.stringify(result).includes('private'));assert.ok(!JSON.stringify(result).includes('secret'));
assert.equal(normalizeLimits({rateLimits:{limitId:'old',primary:{usedPercent:25}}}).buckets[0].primary.remainingPercent,75);
assert.equal(normalizeLimits({}).state,'unavailable');console.log('OpenAI quota normalization and privacy: OK');
