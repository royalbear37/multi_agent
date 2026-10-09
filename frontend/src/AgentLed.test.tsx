import {fireEvent,render,screen} from '@testing-library/react';
import {expect,test} from 'vitest';
import {DrugOverview,WorkflowStep,RunIssues} from './Insights';
import {RiskDetails,AgentStep,EvidenceCoverage,AgentDrugTable} from './AgentLed';
import {CandidateEvidence,EvidenceSourceNotice} from './ClinicalContext';

test('source linkage errors stay visible while invalid original assertions remain folded',()=>{
 render(<AgentDrugTable run={{drug_assessments:[{drug_code:'a',status:'pending',ast_available:true,
  ast:{assessment:'unknown',reason:'藥敏來源欄位未核對',model_reason:'無依據的敏感推論',source_validation:{status:'unconfirmed'}},
  reason:'整合引用錯誤，非病例缺漏',model_reason:'無依據的建議',reference_validation:{status:'unconfirmed'}
 }]}}/>);
 expect(screen.getByText('藥敏來源欄位未核對')).toBeVisible();
 expect(screen.getByText('整合引用錯誤，非病例缺漏')).toBeVisible();
 expect(screen.getByText('無依據的敏感推論')).not.toBeVisible();
 expect(screen.getByText('無依據的建議')).not.toBeVisible();
});

test('legacy AST validation warning does not unfold its original positive assertion',()=>{
 render(<AgentDrugTable run={{drug_assessments:[{drug_code:'ertapenem',status:'pending',ast_available:true,
  ast:{assessment:'unknown',reason:'原始MIC低所以敏感，適合使用；來源未核對',source_validation:{status:'unconfirmed'}},reason:'待確認'
 }]}}/>);
 expect(screen.getByText(/藥敏類別來源尚未通過核對/)).toBeVisible();
 expect(screen.getByText('原始MIC低所以敏感，適合使用；來源未核對')).not.toBeVisible();
});

test('independent audit distinguishes AST source verification from clinical support',()=>{
 render(<AgentDrugTable run={{drug_assessments:[{drug_code:'tetracycline',status:'pending',reason:'引用待核對',
  audit:{verdict:'uncertain',reason:'來源不符',ast_check:{assessment:'resistant'},ast_check_validation:{status:'confirmed'},
         provenance_issues:['引文沒有本藥名稱']}
 }]}}/>);
 fireEvent.click(screen.getByText('查看模型證據草稿（尚非建議）'));
 expect(screen.getByText(/獨立藥敏來源核對：來源欄位一致；類別：抗藥/)).toBeVisible();
 expect(screen.getByText(/這不代表藥品適用性已確認/)).toBeVisible();
 expect(screen.getByText('引用／來源待確認：引文沒有本藥名稱')).toBeVisible();
});

test('confirmed unknown source does not imply a confirmed susceptible claim',()=>{
 render(<AgentDrugTable run={{drug_assessments:[{drug_code:'ertapenem',status:'pending',reason:'待確認',
  audit:{verdict:'uncertain',ast_check:{assessment:'unknown',claim_assessment:'susceptible'},
   ast_check_validation:{status:'unconfirmed',source_status:'confirmed',claim_status:'unconfirmed'}}
 }]}}/>);
 fireEvent.click(screen.getByText('查看模型證據草稿（尚非建議）'));
 expect(screen.getByText(/獨立藥敏來源核對：來源欄位一致；類別：未知/)).toBeVisible();
 expect(screen.getByText('複核辨識的原聲明判讀：敏感；與來源比對：尚未一致。')).toBeVisible();
});

test('original artifact retains its own title when an excerpt is also present',()=>{
 const full={doc_id:'full',document_title:'WHO full book',source_document_id:'same'};
 render(<EvidenceSourceNotice item={full} evidence={[full,{doc_id:'part',document_title:'WHO chapter',source_document_id:'same'}]}/>);
 expect(screen.getByText(/同一原始文件：WHO full book。/)).toBeVisible();
 expect(screen.queryByText(/同一原始文件：WHO chapter/)).toBeNull();
});

test('linked original and excerpt are not presented as independent evidence',()=>{
 const evidence=[
  {chunk_id:'full',doc_id:'original',document_title:'WHO full book',source_document_id:'sha256:one'},
  {chunk_id:'excerpt',doc_id:'part',document_title:'WHO lower UTI',source_document_id:'sha256:one',source_derivation:{original_title:'WHO full book',original_version:'2022'}}
 ];
 render(<CandidateEvidence refs={['excerpt']} evidence={evidence}/>);
 fireEvent.click(screen.getByText(/WHO lower UTI ·/));
 expect(screen.getByText(/同一原始文件：WHO full book · 版本 2022/)).toBeVisible();
 expect(screen.getByText(/不能視為多份獨立證據/)).toBeVisible();
});

test('historical snapshots without lineage are not guessed from matching titles',()=>{
 render(<CandidateEvidence refs={['old']} evidence={[{chunk_id:'old',doc_id:'a',document_title:'WHO'},{chunk_id:'other',doc_id:'b',document_title:'WHO'}]}/>);
 expect(screen.queryByText(/同一原始文件/)).toBeNull();
});

test('retrieval coverage distinguishes absent evidence from omitted input',()=>{
 render(<EvidenceCoverage run={{evidence_coverage:[
  {agent_id:'evidence_agent',stage:'infection',drug_code:'amoxicillin',retrieval_status:'ok',retrieved_count:2,selected_count:1,evidence_refs:['one'],omitted_refs:['two']},
  {agent_id:'clinical_agent',stage:'clinical',drug_code:'nitrofurantoin',retrieval_status:'no_results',retrieved_count:0,selected_count:0,evidence_refs:[],omitted_refs:[]}
 ],evidence_snapshots:[]}}/>);
 fireEvent.click(screen.getByText('逐藥證據準備與呼叫情況'));
 expect(screen.getByText('未找到片段')).toBeVisible();
 expect(screen.getByText('未納入片段（輸入長度限制）')).toBeVisible();
 expect(screen.getByText(/不代表支持用藥/)).toBeVisible();
});

test.each([
 [{status:'failed',attempts:[]},'未呼叫模型'],
 [{status:'failed',attempts:[{status:'failed'}]},'已嘗試呼叫；尚未確認收到回覆'],
 [{status:'failed',attempts:[{status:'failed',usage:{total_tokens:10}}]},'已收到模型回覆；不代表核對通過'],
 [{is_mock:true,attempts:[{status:'completed'}]},'Mock 流程，未呼叫外部模型']
])('prepared references do not imply model delivery: %s',(node,label)=>{
 render(<EvidenceCoverage run={{nodes:[{node_id:'evidence_agent',...node}],evidence_coverage:[
  {agent_id:'evidence_agent',stage:'infection',retrieval_status:'conflict',warnings:['document_version_conflict'],retrieved_count:0,selected_count:0,evidence_refs:[],omitted_refs:[]}
 ]}}/>);
 fireEvent.click(screen.getByText('逐藥證據準備與呼叫情況'));
 expect(screen.getByText(label)).toBeVisible();
 expect(screen.getByText('文件版本衝突：請指定文件版本後重跑')).toBeVisible();
 expect(screen.getByText('同名文件有多個版本；請在病例文件範圍指定版本後重跑。')).toBeVisible();
 expect(screen.queryByText('送入')).toBeNull();
});

test('agent workflow shows drug-specific pending reasons without rule terminology',()=>{
 const run={decision_basis:'agent',retrievals:[],evidence_snapshots:[],drug_assessments:[{drug_code:'amoxicillin',status:'pending',ast_available:false,reason:'缺少支持片段',source_ast:[],clinical:{status:'unknown',allergy:'未確認',renal:'缺測量',interactions:'未確認'},evidence:{status:'uncertain'}}]};
 render(<DrugOverview run={run}/>);
 expect(screen.getByRole('heading',{name:'逐藥決策表'})).toBeVisible();
 expect(screen.getByText(/指引選項；本例未測 AST/)).toBeVisible();
 expect(screen.getByText('尚未通過完整核對，不能視為用藥建議。')).toBeVisible();
 expect(screen.getByText('缺少支持片段')).not.toBeVisible();
 fireEvent.click(screen.getByText('整合草稿與限制（尚非建議）'));
 expect(screen.getByText('缺少支持片段')).toBeVisible();
 expect(screen.queryByText(/通過規則|規則排除/)).toBeNull();
});

test('partial result keeps valid specialist report and actionable issues',()=>{
 const node={agent_id:'ast_agent',node_id:'ast_agent',status:'completed',attempts:[{}],output:{findings:['原始與衍生判讀不一致'],rapid_assessment:'菌名一致',resistance_assessment:'群體統計不能替代 AST',issues:[{field:'AST',impact:'不能確認此藥敏感',action:'核對原報告'}]}};
 render(<><WorkflowStep node={node} index={1} run={{decision_basis:'agent',evidence_snapshots:[]}}/><RunIssues run={{decision_basis:'agent',confirmation_items:[{field:'renal',impact:'不能判斷腎功能風險',action:'補檢驗時間'}]}}/></>);
 expect(screen.getByText('原始與衍生判讀不一致')).toBeInTheDocument();
 expect(screen.getByText('補檢驗時間')).toBeVisible();
});

test('risk dimensions show their own facts, source and next action',()=>{
 const risk={quotes:[{chunk_id:'renal-source',quote:'Original renal precaution text.'}],risk_details:{
   renal:{status:'caution',reason:'已核對測量，仍有一般注意事項',fact_refs:['renal.crcl'],
     evidence_refs:['renal-source'],missing_fields:[],next_action:'人工核對後續追蹤'}
 }};
 render(<RiskDetails risk={risk} run={{evidence_snapshots:[{chunk_id:'renal-source',document_title:'藥品標示',location:{page:3}}]}}/>);
 fireEvent.click(screen.getByText('腎功能初評：需注意'));
 expect(screen.getByText('病例依據：CrCl')).toBeVisible();
 expect(screen.getByText('下一步：人工核對後續追蹤')).toBeVisible();
 fireEvent.click(screen.getByText('藥品標示 · 第 3 頁'));
 expect(screen.getByText('Original renal precaution text.')).toBeVisible();
});

test('empty audit does not look completed or approved',()=>{
 render(<AgentStep index={5} node={{node_id:'evidence_audit',status:'not_applicable',skip_reason:'no_claims',attempts:[]}} run={{}}/>);
 fireEvent.click(screen.getByText(/無可複核聲明，未執行/));
 expect(screen.getByText(/不算複核通過/)).toBeVisible();
 expect(screen.queryByText(/已執行/)).toBeNull();
});

test('legacy supported match labels without audit quotes are explicitly unverified',()=>{
 render(<DrugOverview run={{decision_basis:'agent',drug_assessments:[{drug_code:'a',status:'pending',source_ast:[],
   audit:{verdict:'uncertain',basis:'mixed',infection_match:'supported',population_match:'supported',drug_match:'supported',quotes:[]}}]}}/>);
 fireEvent.click(screen.getByText('查看模型證據草稿（尚非建議）'));
 expect(screen.getByText('本次複核沒有選取引文；上述模型細項不能視為已通過文件核對。')).toBeVisible();
});

test('clinical failure distinguishes supplied case data from unavailable conclusions',()=>{
 render(<AgentStep index={3} node={{node_id:'clinical_agent',status:'failed',attempts:[{status:'failed'}],errors:[{code:'AGENT_SCHEMA_INVALID'}]}}
  run={{case_snapshot:{allergies:{status:'known_none'},renal:{crcl:84.1,egfr:92},medication_history_status:'reviewed_none'}}}/>);
 fireEvent.click(screen.getByText(/臨床風險 Agent · 執行失敗/));
 expect(screen.getByText(/病例快照已有 過敏狀態、CrCl、eGFR、用藥清單完整性/)).toBeVisible();
 expect(screen.getByText(/回覆未通過格式或來源檢核/)).toBeVisible();
});

test('empty agent issue list does not conceal unresolved drug rows',()=>{
 render(<AgentStep index={2} node={{node_id:'evidence_agent',status:'needs_confirmation',output:{issues:[],drugs:[{drug_code:'a',status:'uncertain',reason:'族群不符'}]}}} run={{}}/>);
 fireEvent.click(screen.getByText(/證據 Agent · 需確認/));
 expect(screen.getByText(/逐藥結果有 1 項需注意或尚未完成核對/)).toBeVisible();
 expect(screen.queryByText('此步驟未列出額外待確認事項。')).toBeNull();
});

test.each(['agent-led-1.4.0','agent-led-1.4.1','agent-led-1.4.2','agent-led-1.5.0','agent-led-1.5.1'])('new layered table %s shows a review option once with risk gaps and distinct claim checks',(version)=>{
 const row={drug_code:'option_a',status:'pending',result_tier:'review_option',ast_available:false,source_ast:[],
   blockers:[{kind:'case_data_missing',dimension:'renal',detail:'腎功能檢驗時間未提供'}],
   audit:{verdict:'uncertain',basis:'mixed',quotes:[],claim_checks:[{dimension:'infection',verdict:'supported',reason:'感染來源已核對',evidence_refs:[]},{dimension:'renal',verdict:'uncertain',reason:'風險尚待核對',evidence_refs:[]}]}};
 render(<DrugOverview run={{decision_basis:'agent',versions:{workflow:version},drug_assessments:[row],output:{pending:[row],review_options:[row]}}}/>);
 expect(screen.getAllByText('option_a')).toHaveLength(1);
 expect(screen.getByText(/不能直接接受為完成建議/)).toBeVisible();
 expect(screen.getByText('腎功能檢驗時間未提供')).toBeVisible();
 expect(screen.getByText(/本例未測 AST/)).toBeVisible();
 fireEvent.click(screen.getByText('查看模型證據草稿（尚非建議）'));
 expect(screen.getByText('感染來源已核對')).toBeVisible();
 expect(screen.getByText('風險尚待核對')).toBeVisible();
});

test('zero review options and incomplete risk input do not read as confirmed support',()=>{
 const row={drug_code:'risk_a',status:'pending',result_tier:'pending',ast_available:true,source_ast:[],
   clinical:{status:'no_identified_risk',risk_details:{renal:{status:'no_identified_risk',reason:'模型初评',fact_refs:[],evidence_refs:[]}}},
   blockers:[{kind:'input_omitted',dimension:'renal',detail:'來源未完整提供'}]};
 render(<AgentDrugTable run={{versions:{workflow:'agent-led-1.4.2'},drug_assessments:[row],evidence_snapshots:[]}}/>);
 expect(screen.queryByText(/感染適用性已有支持/)).toBeNull();
 expect(screen.getByText(/0 項有證據的待審閱選項/)).toBeVisible();
 expect(screen.getByText(/尚未完成整體核對，不能解讀為已排除風險/)).toBeVisible();
 expect(screen.getByText(/部分來源片段未提供/)).toBeVisible();
 expect(screen.getByText(/腎功能初評/)).toBeVisible();
});
