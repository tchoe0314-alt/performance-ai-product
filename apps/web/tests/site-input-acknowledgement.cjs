(async()=>{
 const {default:assert}=await import('node:assert/strict');const {default:fs}=await import('node:fs');
 const {default:ts}=await import('typescript');const {default:vm}=await import('node:vm');
 const exports={};const code=ts.transpileModule(fs.readFileSync(`${__dirname}/../app/utils/siteInputAcknowledgement.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
 vm.runInThisContext(`(function(exports){${code}\n})`)(exports);
 const merge=exports.reconcileAcknowledgedSiteInputs;
 const cases=[
 ['accepted source insertion reaches an otherwise unchanged live view',()=>assert.deepEqual(merge({address:'A'},{address:'A'},{address:'A',detection_scale:{scale_ft_per_px:2}}),{address:'A',detection_scale:{scale_ft_per_px:2}})],
 ['newer live address wins over an older response',()=>assert.deepEqual(merge({address:'A'},{address:'C'},{address:'B'}),{address:'C'})],
 ['independent nested source edits both survive',()=>assert.deepEqual(merge({source:{one:1,two:2}},{source:{one:3,two:2}},{source:{one:1,two:4}}),{source:{one:3,two:4}})],
 ['accepted deletion applies when live field is unchanged',()=>assert.deepEqual(merge({source:'old'},{source:'old'},{}),{})],
 ['newer live deletion is not resurrected',()=>assert.deepEqual(merge({source:'old'},{},{source:'accepted'}),{})],
 ['changed arrays remain live, not concatenated or replaced',()=>assert.deepEqual(merge({sources:[1]},{sources:[2]},{sources:[3]}),{sources:[2]})],
 ['changed types remain live',()=>assert.deepEqual(merge({source:{a:1}},{source:null},{source:{a:2}}),{source:null})],
 ['key order is not an engineering change',()=>assert.deepEqual(merge({source:{a:1,b:2}},{source:{b:2,a:1}},{source:{a:3,b:2}}),{source:{a:3,b:2}})],
 ['inputs and returned receipts do not alias',()=>{const a={source:{a:1}},b={source:{a:1}},c={source:{a:2}};const before=JSON.stringify([a,b,c]);const out=merge(a,b,c);out.source.a=5;assert.equal(JSON.stringify([a,b,c]),before);}],
 ['prototype-like JSON keys stay ordinary own data',()=>{const saved=JSON.parse('{"source":{"__proto__":{"polluted":true},"constructor":"literal"}}');const out=merge({source:{}},{source:{newer:true}},saved);assert.equal(Object.getPrototypeOf(out.source),Object.prototype);assert.equal(Object.hasOwn(out.source,'__proto__'),true);assert.equal(out.source.polluted,undefined);assert.equal(out.source.constructor,'literal');}],
 ];let failures=0;for(const [name,run]of cases){try{run();console.log(`PASS ${name}`);}catch(error){failures++;console.error(`FAIL ${name}: ${error.message}`);}}process.exitCode=failures?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
