<?xml version="1.0" encoding="UTF-8"?>
<!-- https://svn.jenkins-ci.org/trunk/hudson/dtkit/dtkit-format/dtkit-junit-model/src/main/resources/com/thalesgroup/dtkit/junit/model/xsd/junit-4.xsd -->
<!-- http://stackoverflow.com/questions/4922867/junit-xml-format-specification-that-hudson-supports -->
<!-- http://stackoverflow.com/questions/721963/xslt-counting-elements-with-a-given-value -->

<xsl:stylesheet version="1.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:fn="http://www.w3.org/2005/xpath-functions">

<xsl:output method="xml" indent="yes"/>

<xsl:template match="/">

<testsuites>
<xsl:attribute name="name">  <xsl:value-of select="/status/plan/name"/></xsl:attribute>
<xsl:apply-templates select="/status/plan/job_layouts" />
</testsuites>

</xsl:template>

<xsl:template match="job_layouts">
<!-- Is mapped to an Igor job -->
<testsuite>
  <xsl:variable name="id" select="position()" />
  <xsl:variable name="job" select="/status/jobs[$id]" />
  <xsl:attribute name="name">     <xsl:value-of select="testsuite"/></xsl:attribute>
  <xsl:attribute name="package">  <xsl:value-of select="/status/plan/name"/></xsl:attribute>
  <xsl:attribute name="hostname"> <xsl:value-of select="$job/host"/></xsl:attribute>
  <xsl:attribute name="id">       <xsl:value-of select="$job/id"/></xsl:attribute>
  <xsl:attribute name="time">     <xsl:value-of select="$job/runtime"/></xsl:attribute>
  <xsl:attribute name="timestamp"><xsl:value-of select="$job/created_at"/></xsl:attribute>
  <xsl:attribute name="tests">
    <xsl:value-of select="count($job//testcases)"/>
  </xsl:attribute>
  <xsl:attribute name="failures">
    <xsl:value-of select="count(/status/jobs/results/is_success[text()='False'])"/>
  </xsl:attribute>
  <xsl:attribute name="errors">0</xsl:attribute>
  <properties>
    <property name="description">
      <xsl:attribute name="value"><xsl:value-of select="/status/plan/description"/></xsl:attribute>
    </property>
    <property name="host">
      <xsl:attribute name="value"><xsl:value-of select="host"/></xsl:attribute>
    </property>
    <property name="profile">
      <xsl:attribute name="value"><xsl:value-of select="profile"/></xsl:attribute>
    </property>
    <property name="additional_kargs">
      <xsl:attribute name="value"><xsl:value-of select="additional_kargs"/></xsl:attribute>
    </property>
    <property name="timeout">
      <xsl:attribute name="value"><xsl:value-of select="$job/timeout"/></xsl:attribute>
    </property>
    <property name="status">
      <xsl:attribute name="value"><xsl:value-of select="$job/state"/></xsl:attribute>
    </property>
  <!--xsl:value-of select="$job/id"/>
  <xsl:value-of select="$job/state"/-->
  </properties>
  <xsl:for-each select="$job/testsuite/testsets/testcases">
    <xsl:sort select="created_at" order="descending"/>
    <xsl:call-template name="testcase-result" select=".">
      <xsl:with-param name="job" select="$job" />
    </xsl:call-template>
  </xsl:for-each>
</testsuite>
</xsl:template>


<xsl:template name="testcase-result">
<xsl:param name="job" />
<testcase>
  <xsl:variable name="id" select="position()" />
  <xsl:variable name="result" select="$job/results[$id]" />
  <xsl:attribute name="name"><xsl:value-of select="name"/></xsl:attribute>
  <xsl:attribute name="time"><xsl:value-of select="$result/runtime"/></xsl:attribute>
  <xsl:if test="/status/status = 'running' and count($job/results)+1 = $id">
    <error>
    <xsl:attribute name="message">Running, awaiting results</xsl:attribute>
    </error>
  </xsl:if>
  <xsl:if test="/status/status = 'running' and count($job/results)+1 &lt; $id">
    <error>
    <xsl:attribute name="message">Queued</xsl:attribute>
    </error>
  </xsl:if>
  <xsl:if test="$result/is_passed = 'False'">
    <failure>
    <xsl:attribute name="type"><xsl:value-of select="$result/note"/></xsl:attribute>
    </failure>
  </xsl:if>
  <xsl:if test="/status/status = 'stopped' and count($job/results) &lt; $id">
    <skipped>
    <xsl:attribute name="message">Skipped because a prior testcase failed</xsl:attribute>
    </skipped>
  </xsl:if>
  <system-out><![CDATA[]]></system-out>
  <system-err><![CDATA[]]></system-err>
</testcase>
</xsl:template>

</xsl:stylesheet> 
<!-- vim: sw=2 -->
