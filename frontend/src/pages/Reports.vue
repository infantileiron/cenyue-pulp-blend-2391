<script setup lang="ts">
import {ref,computed,onMounted} from 'vue';
import {reviews} from '../stores/reviews';
import {reports} from '../stores/reports';
import {isAdmin,canWrite,auth} from '../stores/auth';
import {downloadCsv} from '../api/client';
import {decideReview,resubmitReview} from '../api/reviews';
import {useTask} from '../hooks/useTask';
import {reviewEventLabels} from '../constants/enums';
import type {FormulaReview,ReviewEvent} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import StatusPill from '../components/common/StatusPill.vue';
import QualityTable from '../components/QualityTable.vue';
import {fixed} from '../utils/format';

const expanded=ref('');
const rejectFor=ref('');
const rejectComment=ref('');
const resubmitFor=ref('');
const resubmitAction=ref('');
const workingId=ref('');
const {error,busy,act}=useTask();
onMounted(()=>Promise.all([reviews.load(),reports.load()]));

const sorted=computed(()=>[...reviews.items.value].sort((a,b)=>
 (b.created_at||'').localeCompare(a.created_at||'')));

function stamp(iso:string){return iso?iso.replace('T',' ').replace('Z',' UTC'):''}
// 升级前的在途复核没有 created_by，归属不可考：放开给任意可写账号代为撤回/重提，避免流程卡死
function isMine(r:FormulaReview){return r.created_by===auth.user?.email || !r.created_by}

async function refresh(){await Promise.all([reviews.load(),reports.load()])}

function decide(r:FormulaReview,decision:'approve'|'withdraw'|'reject',comment=''){
 workingId.value=r.id;
 act(async()=>{
  // 始终以服务端版本为准提交；版本已变（过期页面）时后端返回409并提示刷新
  await decideReview(r.id,decision,r.version,comment);
  rejectFor.value='';rejectComment.value='';
  await refresh();
 }).finally(()=>{workingId.value=''});
}
function openReject(r:FormulaReview){rejectFor.value=r.id;rejectComment.value=''}
function submitReject(r:FormulaReview){
 if(!rejectComment.value.trim())return;
 decide(r,'reject',rejectComment.value.trim());
}
function openResubmit(r:FormulaReview){resubmitFor.value=r.id;resubmitAction.value=r.action}
function submitResubmit(r:FormulaReview){
 workingId.value=r.id;
 act(async()=>{
  await resubmitReview(r.id,resubmitAction.value);
  resubmitFor.value='';
  await refresh();
 }).finally(()=>{workingId.value=''});
}
function publish(r:FormulaReview){
 workingId.value=r.id;
 act(async()=>{
  await reports.create({review_id:r.id,title:'原浆配方底稿 '+new Date().toLocaleDateString()});
  await refresh();
 }).finally(()=>{workingId.value=''});
}
function reportOf(r:FormulaReview){return reports.items.value.find(x=>x.review_id===r.id)}
function download(id:string,samples=false){act(()=>downloadCsv(id,samples))}
</script>

<template>
 <PageHeading index="05 / 配方归档" title="留住比例、波动假设和每一次复核判断。"
  note="批准/撤回/驳回并发到达时只接受一个结果；过期页面的操作会明确失败。归档只固化当次已批准结论，重复归档仍是同一份快照，不随后续修改变化。"/>
 <Notice :message="error"/>
 <div class="two-col">
  <section>
   <h2>配方复核处理记录</h2>
   <article v-for="r in sorted" :key="r.id" class="review-row">
    <div class="review-meta">
     <StatusPill :status="r.state"/>
     <span class="version-tag">第 {{r.version}} 版</span>
     <small>运行 {{r.run_id.slice(0,8)}} · 提交人 {{r.created_by||'历史记录'}}</small>
    </div>
    <p>{{r.action}}</p>
    <ul class="event-timeline">
     <li v-for="e in r.events as ReviewEvent[]" :key="e.id">
      <time>{{stamp(e.created_at)}}</time>
      <b>{{reviewEventLabels[e.action]||e.action}}</b>
      <span class="event-comment">
       <span class="event-actor">{{e.actor||'系统'}}</span>
       <template v-if="e.comment">：{{e.comment}}</template>
       <small v-if="e.detail?.version">（第{{e.detail.version}}版）</small>
      </span>
     </li>
    </ul>

    <div v-if="canWrite() && r.state==='submitted'" class="actions">
     <button v-if="isAdmin()" :disabled="busy||workingId===r.id" @click="decide(r,'approve')">批准配方复核</button>
     <button v-if="isAdmin()" class="secondary" :disabled="busy||workingId===r.id" @click="openReject(r)">驳回并要求修改</button>
     <button v-if="isMine(r)" class="secondary" :disabled="busy||workingId===r.id" @click="decide(r,'withdraw')">撤回复核</button>
    </div>

    <form v-if="isAdmin() && rejectFor===r.id" class="editor-panel" @submit.prevent="submitReject(r)">
     <label>驳回意见（将完整保留给提交人，必填）
      <textarea v-model="rejectComment" required minlength="2" maxlength="3000" rows="4"
       placeholder="说明结论的问题与修改方向"></textarea>
     </label>
     <div class="actions">
      <button :disabled="busy" type="submit">确认驳回</button>
      <button type="button" class="secondary" @click="rejectFor=''">取消</button>
     </div>
    </form>

    <div v-if="canWrite() && (r.state==='withdrawn'||r.state==='rejected') && isMine(r)" class="actions">
     <button class="secondary" :disabled="busy||workingId===r.id" @click="openResubmit(r)">修改后重新提交</button>
    </div>
    <form v-if="resubmitFor===r.id" class="editor-panel" @submit.prevent="submitResubmit(r)">
     <label>修改后的复核说明（原意见与处理记录保留，版本递增至第{{r.version+1}}版）
      <textarea v-model="resubmitAction" required minlength="8" maxlength="3000" rows="6"></textarea>
     </label>
     <div class="actions">
      <button :disabled="busy" type="submit">重新提交复核</button>
      <button type="button" class="secondary" @click="resubmitFor=''">取消</button>
     </div>
    </form>

    <div v-if="isAdmin() && r.state==='approved'" class="actions">
     <button class="secondary" :disabled="busy||workingId===r.id" @click="publish(r)">
      {{reportOf(r)?'重新归档（返回同一份快照）':'生成配方快照'}}
     </button>
    </div>
   </article>
  </section>

  <section>
   <h2>批准底稿（不可变快照）</h2>
   <article v-for="x in reports.items.value" :key="x.id" class="report-row">
    <p class="eyebrow">APPROVED FORMULA RECORD · 第{{x.snapshot.review_version??1}}版结论</p>
    <h3>{{x.title}}</h3>
    <p>
     名义成本{{fixed(x.snapshot.result.lp.nominal_cost)}}元/吨 ·
     模拟通过{{x.snapshot.result.robustness.passed}}/{{x.snapshot.result.robustness.n_samples}}
    </p>
    <small v-if="x.snapshot.review_id">关联复核 {{String(x.snapshot.review_id).slice(0,8)}} ·
     批准人 {{x.snapshot.reviewer}}<template v-if="!x.snapshot.review_version"> · 历史归档结构</template></small>
    <div class="actions">
     <button @click="download(x.id)">下载配方 CSV ↓</button>
     <button class="secondary" @click="download(x.id,true)">下载扰动样本</button>
     <button class="secondary" @click="expanded=expanded===x.id?'':x.id">质量快照</button>
    </div>
    <QualityTable v-if="expanded===x.id" :rows="x.snapshot.result.lp.qualities"/>
   </article>
  </section>
 </div>
</template>
