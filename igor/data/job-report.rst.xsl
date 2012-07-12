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
                       Igor Job Report
===============================================================

Report created on <xsl:value-of select="date:date-time()"/> 
by igor &lt;http://gitorious.org/ovirt/igord&gt;

------


Summary
---------------------------------------------------------------
- State: **<xsl:value-of select="/status/state/text()"/>**
- Runtime: <xsl:value-of select="/status/runtime/text()"/> / <xsl:value-of select="/status/timeout/text()"/>
- Testsuite: <xsl:value-of select="/status/testsuite/name/text()"/>
- Profile: <xsl:value-of select="/status/profile/text()"/>
- Host: <xsl:value-of select="/status/host/text()"/>
- ID: <xsl:value-of select="/status/id/text()"/>


Testcase Results
---------------------------------------------------------------
(Format: &lt;Start time&gt; / &lt;Testcase name&gt; : &lt;Passed&gt;)
<xsl:if test="count(//results) = 0">
(None)
</xsl:if>
<xsl:for-each select="//results">
<xsl:variable name="created_at_h" select="date:add('1970-01-01T00:00:00Z', date:duration(created_at/text()))"/>
#. <xsl:value-of select="$created_at_h"/> / <xsl:value-of select="testcase/name/text()"/>: <xsl:value-of select="is_passed/text()"/>
</xsl:for-each>


Artifacts
---------------------------------------------------------------
Created artifacts:
<xsl:if test="count(//artifacts) = 0">
(None)
</xsl:if>
<xsl:for-each select="//artifacts">
- <xsl:value-of select="text()"/>
</xsl:for-each>


Specification
---------------------------------------------------------------<xsl:for-each select="//testsets">

Testcases in set **<xsl:value-of select="name/text()"/>**:
<xsl:for-each select="testcases">
#. <xsl:value-of select="name/text()"/>
</xsl:for-each><xsl:text>

</xsl:text>
</xsl:for-each>
</xsl:template>

</xsl:stylesheet> 
<!-- vim: sw=2 -->
