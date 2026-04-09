<template>
  <el-container class="app-shell">
    <el-header class="header">
      <div>
        <h1>All-in-one IB Graph Tool</h1>
        <p>Uncertainty among trials; Linearization; error bar; best fit; max/min line; uncertainty of gradient and intercept; proper decimal/s.f.</p>
      </div>
    </el-header>

    <el-main>
      <el-row :gutter="16">
        <el-col :xs="24" :lg="9">
          <el-card shadow="never" class="panel">
            <template #header>Input Information</template>

            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".cmbl"
              :on-change="handleCmbl"
            >
              <el-button type="primary">Import .cmbl</el-button>
            </el-upload>

            <el-divider />

            <el-form label-position="top">
              <el-form-item label="Raw data(compatible with TSV / CSV, For each row: IV, DV1, DV2, DV3...); ENGLISH comma">
                <el-input
                  v-model="rawMatrix"
                  type="textarea"
                  :rows="10"
                  placeholder="Eg:&#10;0.10,1.24,1.23,1.26&#10;0.20,1.78,1.74,1.76"
                />
              </el-form-item>

              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="IV Symbol">
                    <el-input v-model="form.iv_symbol" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="IV Unit">
                    <el-input v-model="form.iv_unit" placeholder="m, s, ms^{-2}" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="DV Symbol">
                    <el-input v-model="form.dv_symbol" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="DV Unit">
                    <el-input v-model="form.dv_unit" placeholder="s, V, m/s" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="IV Abs uncertainty">
                    <el-input-number v-model="form.iv_error" :step="0.01" :min="0" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="DV Abs uncertainty (trial-to-trial)">
                    <el-input-number v-model="form.dv_trial_error" :step="0.01" :min="0" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="X Linearization f(x)">
                    <el-input v-model="form.x_transform" placeholder="x / log(x) / sqrt(x) / x**2" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="Y Linearization f(x)">
                    <el-input v-model="form.y_transform" placeholder="x / log(x) / sqrt(x) / x**2" />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                <el-form-item>Using python math module. x**n==x^n, exp(n)==e^n, log(m,n)==log_n(m) </el-form-item>
                </el-col>
              </el-row>

              <el-space wrap>
                <el-button type="success" @click="runAnalysis">Analyze</el-button>
                <el-button @click="downloadStage1">Step 1 CSV</el-button>
                <el-button @click="downloadStage2">Step 2 CSV</el-button>
                              <el-space wrap>
                <el-button type="primary" plain @click="downloadCmbl">Export CMBL</el-button>
              </el-space>
              </el-space>
            </el-form>
          </el-card>
        </el-col>

        <el-col :xs="24" :lg="15">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="Step 1: Raw Data Table" name="stage1">
              <el-card shadow="never" class="panel">
                <el-table :data="result?.stage1 || []" stripe>
                  <el-table-column prop="iv" label="IV" />
                  <el-table-column prop="error_iv" label="Error IV" />
                  <el-table-column prop="dv" label="DV(avg)" />
                  <el-table-column prop="error_dv" label="Error DV" />
                </el-table>
              </el-card>
            </el-tab-pane>

            <el-tab-pane label="Step 2: Linearized Table" name="stage2">
              <el-card shadow="never" class="panel">
                <el-table :data="result?.stage2 || []" stripe>
                  <el-table-column prop="x" label="Linearized X" />
                  <el-table-column prop="error_x" label="Error X" />
                  <el-table-column prop="y" label="Linearized Y" />
                  <el-table-column prop="error_y" label="Error Y" />
                </el-table>
              </el-card>
            </el-tab-pane>

            <el-tab-pane label="plot" name="plot">
              <el-row :gutter="16">
                <el-col :xs="24" :lg="17">
                  <el-card shadow="never" class="panel">
                    <div ref="plotRef" style="height: 520px"></div>
                  </el-card>
                </el-col>
                <el-col :xs="24" :lg="7">
                  <el-card shadow="never" class="panel">
                    <template #header>Equations</template>
                    <p><b>Best Fit:</b> {{ result?.plot?.best_fit?.eq }}</p>
                    <p><b>Max Line:</b> {{ result?.plot?.max_line?.eq }}</p>
                    <p><b>Min Line:</b> {{ result?.plot?.min_line?.eq }}</p>
                    <el-divider />
                    <p><b>Gradient:</b> {{ result?.plot?.reported?.m }} ± {{ result?.plot?.reported?.dm }}</p>
                    <p><b>Intercept:</b> {{ result?.plot?.reported?.b }} ± {{ result?.plot?.reported?.db }}</p>
                    <p><b>R²:</b> {{ result?.plot?.best_fit?.r2?.toFixed?.(4) }}</p>
                  </el-card>
                </el-col>
              </el-row>
            </el-tab-pane>
          </el-tabs>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import axios from 'axios'
import { analyze, importCmbl, exportCmbl } from './api'
import { nextTick, reactive, ref } from 'vue'
import Plotly from 'plotly.js-dist-min'
import { ElMessage } from 'element-plus'


const activeTab = ref('stage1')
const plotRef = ref<HTMLDivElement | null>(null)
const rawMatrix = ref('')

const form = reactive({
  iv_symbol: 'x',
  iv_unit: '',
  dv_symbol: 'y',
  dv_unit: '',
  iv_error: 0.01,
  dv_trial_error: 0.01,
  x_transform: 'x',
  y_transform: 'x',
})

const result = ref<any>(null)

function parseMatrix(text: string) {
  const rows = text
    .trim()
    .split(/\n+/)
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => line.split(/[\t,; ]+/).map(Number))

  const iv_values = rows.map(r => r[0])
  const dv_trials = rows.map(r => r.slice(1))
  return { iv_values, dv_trials }
}

async function runAnalysis() {
  try {
    const parsed = parseMatrix(rawMatrix.value)
    const payload = {
      ...form,
      iv_values: parsed.iv_values,
      dv_trials: parsed.dv_trials,
    }
    result.value = await analyze(payload)
    activeTab.value = 'plot'
    await nextTick()
    drawPlot()
    ElMessage.success('Anaysis completed!')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err.message || 'Failed to analyze')
  }
}

async function handleCmbl(uploadFile: any) {
  try {
    const data = await importCmbl(uploadFile.raw)
    const lines: string[] = []
    for (let i = 0; i < data.data.x.length; i++) {
      lines.push([data.data.x[i], data.data.y[i]].join(','))
    }
    rawMatrix.value = lines.join('\n')
    form.iv_symbol = data.axis.x_name || 'x'
    form.dv_symbol = data.axis.y_name || 'y'
    form.iv_unit = data.axis.x_unit || ''
    form.dv_unit = data.axis.y_unit || ''
    activeTab.value = 'plot'

    await nextTick()
    const funcs = data.functions || []
    const best = funcs.find((f: any) => f.short_name === 'Linear') || funcs[0]

    Plotly.react(plotRef.value!, [
      {
        x: data.data.x,
        y: data.data.y,
        mode: 'markers',
        type: 'scatter',
        name: 'Data',
        error_x: { type: 'data', array: data.data.error_x, visible: true },
        error_y: { type: 'data', array: data.data.error_y, visible: true },
      }
    ], {
      margin: { l: 60, r: 20, t: 20, b: 60 },
      xaxis: { title: `${data.axis.x_name}${data.axis.x_unit ? ` (${data.axis.x_unit})` : ''}` },
      yaxis: { title: `${data.axis.y_name}${data.axis.y_unit ? ` (${data.axis.y_unit})` : ''}` },
    }, { responsive: true })

    if (best) {
      ElMessage.success('CMBL Imported!')
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err.message || 'Fail to import CMBL')
  }
}

function drawPlot() {
  if (!plotRef.value || !result.value) return
  const p = result.value.plot
  const meta = result.value.meta
  const x = p.x
  const minX = Math.min(...x)
  const maxX = Math.max(...x)
  
  // 向两边稍微延伸一点画线，不至于线被切断
  const margin = (maxX - minX) * 0.05
  const xLine = [minX - margin, maxX + margin]

  const lineY = (m: number, b: number) => xLine.map(v => m * v + b)

  // 拼接轴标签与单位：例如 "lg d (m)" 或者 "T^2 (s^2)"
  const xTitle = meta.x_unit ? `${meta.x_label} (${meta.x_unit})` : meta.x_label
  const yTitle = meta.y_unit ? `${meta.y_label} (${meta.y_unit})` : meta.y_label

  Plotly.react(plotRef.value, [
    {
      x: p.x,
      y: p.y,
      mode: 'markers',
      type: 'scatter',
      name: 'Data',
      marker: { size: 8, color: '#c0392b' },
      error_x: { type: 'data', array: p.error_x, visible: true, thickness: 1.5 },
      error_y: { type: 'data', array: p.error_y, visible: true, thickness: 1.5 },
    },
    {
      x: xLine,
      y: lineY(p.best_fit.m, p.best_fit.b),
      mode: 'lines',
      type: 'scatter',
      name: 'Best Fit',
      line: { color: '#111', width: 2 },
    },
    {
      x: xLine,
      y: lineY(p.max_line.m, p.max_line.b),
      mode: 'lines',
      type: 'scatter',
      name: 'Max Line',
      line: { color: '#2471a3', dash: 'dash', width: 2 },
    },
    {
      x: xLine,
      y: lineY(p.min_line.m, p.min_line.b),
      mode: 'lines',
      type: 'scatter',
      name: 'Min Line',
      line: { color: '#1e8449', dash: 'dot', width: 2 },
    }
  ], {
    margin: { l: 80, r: 30, t: 30, b: 80 }, // 增加 left 和 bottom 的边距留给标题
    xaxis: {
      title: {
        text: xTitle,
        font: { size: 14, family: 'Arial, sans-serif' },
        standoff: 20 // 让文字离轴线远一点，在下方横着居中
      },
      zeroline: false
    },
    yaxis: {
      title: {
        text: yTitle,
        font: { size: 14, family: 'Arial, sans-serif' },
        standoff: 20 // 让文字离轴线远一点，在左侧竖着居中
      },
      zeroline: false
    },
    legend: { 
      orientation: 'h', 
      y: 1.1, // 把图例放到图表正上方
      x: 0.5,
      xanchor: 'center'
    },
  }, { responsive: true, displayModeBar: true })
}

function downloadCsv(rows: any[], filename: string) {
  if (!rows.length) return
  const headers = Object.keys(rows[0])
  const csv = [
    headers.join(','),
    ...rows.map(r => headers.map(h => JSON.stringify(r[h] ?? '')).join(','))
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

function downloadStage1() {
  downloadCsv(result.value?.stage1 || [], 'stage1_iv_dv_errors.csv')
}

function downloadStage2() {
  downloadCsv(result.value?.stage2 || [], 'stage2_linearized.csv')
}

async function downloadCmbl() {
  if (!result.value) {
    ElMessage.warning('Please run Step 1 and 2 first!')
    return
  }
  try {
    const payload = {
      x_name: result.value.meta.x_label,
      x_unit: result.value.meta.x_unit,
      y_name: result.value.meta.y_label,
      y_unit: result.value.meta.y_unit,
      x_data: result.value.plot.x,
      y_data: result.value.plot.y,
      error_x: result.value.plot.error_x,
      error_y: result.value.plot.error_y,
      best_fit: result.value.plot.best_fit,
      max_line: result.value.plot.max_line,
      min_line: result.value.plot.min_line
    }

    // 直接收二进制 Blob，不解析 JSON
    const res = await axios.post('/api/export-cmbl', payload, { responseType: 'blob' })

    const a = document.createElement('a')
    a.href = URL.createObjectURL(res.data)
    a.download = `IB_Graph_${payload.x_name}_vs_${payload.y_name}.cmbl`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('CMBL Exported!')
  } catch (err: any) {
    ElMessage.error(err?.message || 'Fail to export CMBL')
  }
}
</script>

