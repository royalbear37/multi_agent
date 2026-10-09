import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import {expect,test,vi} from 'vitest';
import {AllergyContext,AllergyEditor} from './AllergyContext';

test('old label is shown as unverified rather than confirmed or absent',()=>{
  render(<AllergyContext value={{status:'known_present',items:[{drug_code:'amoxicillin',reaction:'rash'}]}}/>);
  expect(screen.getByText(/有過敏標籤/)).toBeVisible();
  expect(screen.getByText('未提供確認狀態')).toBeVisible();
  expect(screen.getByText('來源未記載')).toBeVisible();
});

test('supplement form retains original label and saves new assessment separately',async()=>{
  const save=vi.fn().mockResolvedValue(undefined);
  const original={status:'known_present',items:[{drug_code:'amoxicillin',reaction:'anaphylaxis',severity:'severe'}]};
  render(<AllergyEditor value={original} busy={false} onSave={save}/>);
  fireEvent.click(screen.getByText('補充過敏紀錄（保存為新病例版本）'));
  fireEvent.change(screen.getByLabelText('標籤來源'),{target:{value:'轉入病歷'}});
  fireEvent.change(screen.getByLabelText('確認狀態'),{target:{value:'conflicting'}});
  fireEvent.click(screen.getByText('保存過敏資料並建立新版本'));
  await waitFor(()=>expect(save).toHaveBeenCalledOnce());
  expect(save.mock.calls[0][0]).toMatchObject({status:'known_present',items:[{
    drug_code:'amoxicillin',reaction:'anaphylaxis',severity:'severe',label_source:'轉入病歷',verification_status:'conflicting'
  }]});
  expect(original.items[0]).not.toHaveProperty('label_source');
});
