import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {test,expect,vi} from 'vitest';
import {PhysicianReview,DrugCautions} from './PhysicianReview';
const run={case_snapshot:{allergies:{status:'known_none',items:[]},medication_history_status:'reviewed_none',renal:{egfr:90}},
 drug_assessments:[{drug_code:'a',status:'pending',ast_available:true,ast:{assessment:'conflicting'},blockers:[{detail:'來源待核對'}],clinical:{status:'caution',risk_details:{allergy:{status:'caution',reason:'一般過敏警語',next_action:'詢問過敏史'}}}},
 {drug_code:'b',status:'avoid',ast_available:true}],evidence_snapshots:[]};

test('pending or avoided drugs remain visible for explicit human decisions without promotion',async()=>{
 const save=vi.fn().mockResolvedValue(undefined);
 render(<PhysicianReview run={run} role="physician" busy={false} onSave={save}/>);
 expect(screen.getByText(/病例已記錄無已知過敏；一般/)).toBeVisible();
 expect(screen.queryByText('模型提醒：詢問過敏史')).toBeNull();
 expect(screen.getByText(/藥敏來源衝突/)).toBeVisible();
 expect(screen.getByText('系統不建議')).toBeVisible();
 const submit=screen.getByRole('button',{name:'保存逐藥決策'});
 expect(submit).toBeDisabled();
 fireEvent.change(screen.getByLabelText('a 醫師決定'),{target:{value:'conditional'}});
 fireEvent.change(screen.getByLabelText('a 決策理由'),{target:{value:'已閱讀限制'}});
 expect(submit).toBeDisabled();
 fireEvent.change(screen.getByLabelText('a 使用條件'),{target:{value:'先處理併用藥限制'}});
 expect(submit).toBeDisabled();
 fireEvent.click(screen.getByRole('checkbox'));
 fireEvent.click(submit);
 await waitFor(()=>expect(save).toHaveBeenCalledWith([{drug_code:'a',decision:'conditional',reason:'已閱讀限制',conditions:'先處理併用藥限制',acknowledged_warnings:true}]));
 expect(run.drug_assessments[0].status).toBe('pending');
});

test('failed saves retain decisions and empty allergy data remains unknown',async()=>{
 render(<PhysicianReview run={{...run,case_snapshot:{}}} role="physician" busy={false} onSave={vi.fn().mockRejectedValue(new Error('保存失敗'))}/>);
 expect(screen.getByText('過敏史尚未確認')).toBeVisible();
 expect(screen.queryByText(/病例已記錄無已知過敏/)).toBeNull();
 fireEvent.change(screen.getByLabelText('b 醫師決定'),{target:{value:'decline'}});
 fireEvent.change(screen.getByLabelText('b 決策理由'),{target:{value:'不採用'}});
 fireEvent.click(screen.getByRole('button',{name:'保存逐藥決策'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('保存失敗');
 expect(screen.getByLabelText('b 決策理由')).toHaveValue('不採用');
});

test('role and reason edits do not bypass warning acknowledgment',()=>{
 const {rerender}=render(<PhysicianReview run={run} role="research" busy={false} onSave={vi.fn()}/>);
 fireEvent.change(screen.getByLabelText('b 醫師決定'),{target:{value:'adopt'}});
 fireEvent.change(screen.getByLabelText('b 決策理由'),{target:{value:'已核對'}});
 fireEvent.click(screen.getByRole('checkbox'));
 expect(screen.getByRole('button',{name:'保存逐藥決策'})).toBeDisabled();
 rerender(<PhysicianReview run={run} role="physician" busy={false} onSave={vi.fn()}/>);
 expect(screen.getByRole('button',{name:'保存逐藥決策'})).toBeEnabled();
 fireEvent.change(screen.getByLabelText('b 決策理由'),{target:{value:'修訂判斷'}});
 expect(screen.getByRole('checkbox')).not.toBeChecked();
});

test('legacy risk text and independent audit problems stay visible before deciding',()=>{
 render(<DrugCautions run={run} row={{status:'pending',ast_available:true,clinical:{allergy:'舊版已記錄嚴重過敏警示',renal:'腎功能需調整',interactions:'不可與某藥併用'},audit:{reason:'引用尚未支持風險结論',provenance_issues:['原文來源不符'],claim_checks:[{dimension:'renal',verdict:'uncertain',reason:'選段不是腎功能章節',validation_issues:['引用另一藥品']}]}}}/>);
 for(const text of ['舊版已記錄嚴重過敏警示','腎功能需調整','不可與某藥併用','原文來源不符','選段不是腎功能章節','引用另一藥品']) expect(screen.getByText(new RegExp(text))).toBeVisible();
 expect(screen.getByText(/不能由空白推定無風險/)).toBeVisible();
 expect(screen.queryByText(/本次初評未列額外注意事項/)).toBeNull();
});

test('allergy history deduplication never removes additional drug restrictions',()=>{
 render(<DrugCautions run={run} row={{status:'pending',ast_available:true,clinical:{risk_details:{allergy:{status:'caution',reason:'需注意',next_action:'詢問過敏史；不可與某藥併用'}}}}}/>);
 expect(screen.getByText('模型提醒：詢問過敏史；不可與某藥併用')).toBeVisible();
});

test('unknown AST remains visibly unverified even when the model draft claims sensitivity',()=>{
 render(<PhysicianReview run={{...run,drug_assessments:[{drug_code:'ertapenem',status:'pending',ast_available:true,ast:{assessment:'unknown'},evidence:{reason:'AST結果顯示敏感'}}]}} role="physician" busy={false} onSave={vi.fn()}/>);
 expect(screen.getByText(/藥敏判讀尚未核實/)).toBeVisible();
 fireEvent.click(screen.getByText('引用與完整初評'));
 expect(screen.getByText(/原始模型初評（須與藥敏及獨立複核分開核對）/)).toBeVisible();
});
