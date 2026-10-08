{{- define "google-opinie.labels" -}}
app.kubernetes.io/name: google-opinie
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "google-opinie.selector" -}}
app.kubernetes.io/name: google-opinie
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
