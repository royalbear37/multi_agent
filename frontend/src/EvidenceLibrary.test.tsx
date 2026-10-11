import {render,screen,fireEvent} from '@testing-library/react';
import {test,expect} from 'vitest';
import {EvidenceLibrary} from './EvidenceLibrary';

test('source text is collapsed by version and searchable without losing original text',()=>{
 render(<EvidenceLibrary run={{evidence_snapshots:[
  {doc_id:'who',document_title:'WHO',document_version:'2022',chunk_id:'1',text:'Original amoxicillin paragraph',location:{page:22}},
  {doc_id:'who',document_title:'WHO',document_version:'2023',chunk_id:'2',text:'Different version',location:{page:24}},
 ]}}/>);
 expect(screen.getByText('Original amoxicillin paragraph')).not.toBeVisible();
 fireEvent.change(screen.getByLabelText('搜尋文件或原文'),{target:{value:'amoxicillin'}});
 expect(screen.queryByText(/2023/)).toBeNull();
 fireEvent.click(screen.getByText('WHO · 2022 · 1 個片段'));
 fireEvent.click(screen.getByText(/第 22 頁 · 片段 1/));
 expect(screen.getByText('Original amoxicillin paragraph')).toBeVisible();
 expect(screen.getByText('開啟原始文件')).toHaveAttribute('href','/api/documents/who/source#page=22');
});

test('full text and excerpt retain shared origin even while searching',()=>{
 render(<EvidenceLibrary run={{evidence_snapshots:[
  {doc_id:'full',document_title:'WHO full book',document_version:'2022',chunk_id:'full',source_document_id:'same',text:'Original full text',is_synthetic:false},
  {doc_id:'part',document_title:'WHO excerpt',document_version:'2022',chunk_id:'part',source_document_id:'same',source_derivation:{original_title:'WHO full book',original_version:'2022'},text:'amoxicillin paragraph',is_synthetic:false}
 ]}}/>);
 fireEvent.change(screen.getByLabelText('搜尋文件或原文'),{target:{value:'amoxicillin'}});
 fireEvent.click(screen.getByText('WHO excerpt · 2022 · 1 個片段'));
 expect(screen.getByText(/同一原始文件：WHO full book/)).toBeVisible();
 expect(screen.getByText(/不能視為多份獨立證據/)).toBeVisible();
});
