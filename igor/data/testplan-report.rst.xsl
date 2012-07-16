<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:fn="http://www.w3.org/2005/xpath-functions"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  xmlns:date="http://exslt.org/dates-and-times">

<xsl:output method="text" indent="no" disable-output-escaping="no"/>
<xsl:strip-space elements="" />
<xsl:preserve-space elements="*" />


<xsl:template match="/">
===============================================================
                     Igor Testplan Report
===============================================================

Report created on <xsl:value-of select="date:date-time()"/> 
by igor &lt;http://gitorious.org/ovirt/igord&gt;

------

Summary
---------------------------------------------------------------
- Testplan: <xsl:value-of select="/status/plan/name"/>
<xsl:if test="/status/passed = 'True'">
- State: **passed**</xsl:if>
<xsl:if test="/status/passed != 'True'">
- State: **failed**</xsl:if>
- Status: <xsl:value-of select="/status/status"/>
- Created at: <xsl:value-of select="/status/created_at"/>
- Runtime: <xsl:value-of select="/status/runtime"/> / <xsl:value-of select="/status/plan/timeout"/>


Layouts &amp; Jobs
---------------------------------------------------------------
A layout specifies the parameters of a planned job.

<xsl:if test="count(/status/plan/job_layouts) = 0">
(None)
</xsl:if>
<xsl:for-each select="/status/plan/job_layouts">
<xsl:value-of select="position()"/>. Layout &amp; Job
```````````````````````````````````````````````````````````````
:Testsuite: <xsl:value-of select="testsuite"/>
:Profile:   <xsl:value-of select="profile"/>
:Host:      <xsl:value-of select="host"/>
:Additional kernel arguments: ``<xsl:value-of select="additional_kargs"/>``
<xsl:if test="count(/status/jobs) >= position()">
<xsl:variable name="id" select="position()" />
<xsl:variable name="job" select="/status/jobs[$id]" />
:Job ID:    <xsl:value-of select="$job/id"/>
:Job State: **<xsl:value-of select="$job/state"/>**
:Job Runtime: <xsl:value-of select="$job/runtime"/> / <xsl:value-of select="$job/timeout"/>
</xsl:if>
<xsl:text>

</xsl:text>
</xsl:for-each>


</xsl:template>

</xsl:stylesheet> 
<!-- vim: sw=2 -->
