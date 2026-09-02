'use strict';
const fs=require('fs'), p=require('path');
const APP='/Users/kevindooley/Claude/Projects/Crawdad/app/js';
const GEN=require(p.join(APP,'generator.js')), P=require(p.join(APP,'parser.js')),
      NET=require(p.join(APP,'network.js')), SCHEMA=require(p.join(APP,'craschema.js')),
      CLEAN=require(p.join(APP,'textclean.js')), STOP=require(p.join(APP,'stopwords.js')),
      TM=require(p.join(APP,'textmetrics.js'));
const porter2=require('wink-porter2-stemmer');
const parser=P.createParser(require('wink-nlp'), require('wink-eng-lite-web-model'), {compromise:require('compromise')});
const deps={parser, porter2, sentiment:require('wink-sentiment'), isStopWord:STOP.isStopWord,
  schema:SCHEMA, network:NET, textclean:CLEAN, textmetrics:TM,
  keyphrases:require(p.join(APP,'keyphrases.js')), communities:require(p.join(APP,'communities.js'))};
const S='/private/tmp/claude-501/-Users-kevindooley/9b7ad386-c9d3-4425-9d58-e9841edc249a/scratchpad/';
const items=JSON.parse(fs.readFileSync(S+'cra-in.json','utf8'));
const out=[];
for (const it of items) {
  let r;
  try { r=GEN.generate('x.txt', it.text, {stemming:true, keepPronouns:false, interSentenceLinking:false, excludeWords:[]}, deps); }
  catch(e) { out.push({n:it.n, code:it.code, error:e.message.slice(0,80)}); continue; }
  const nodes=r.craData.network.nodes.slice().sort((a,b)=>b.influence-a.influence);
  const total=nodes.length;
  // the words of the matched span, stemmed, looked up in the network
  const words=(it.span||'').toLowerCase().split(/[^a-z0-9]+/).filter(w=>w.length>2 && !STOP.isStopWord(w));
  let best=null, bestRank=null;
  for (const w of words) {
    const stem=porter2(w);
    const idx=nodes.findIndex(nd=>nd.word===stem || nd.word===w || nd.display.toLowerCase()===w);
    if (idx>=0 && (best===null || nodes[idx].influence>best)) { best=nodes[idx].influence; bestRank=idx+1; }
  }
  out.push({n:it.n, code:it.code, source:it.source, tech:it.tech, nodes:total,
            span:it.span, words, influence:best, rank:bestRank,
            pctile: (best!==null && total>1) ? 1-(bestRank-1)/(total-1) : null,
            maxInfluence: nodes.length?nodes[0].influence:null});
}
fs.writeFileSync(S+'cra-out.json', JSON.stringify(out));
console.log('processed', out.length, '| errors', out.filter(x=>x.error).length,
            '| span word found in network', out.filter(x=>x.influence!==null).length);
